set -euo pipefail
cd /root/royal_bot
TS="$(date +%Y%m%d-%H%M%S)"

echo "==[1] stop tgbot =="
systemctl stop tgbot || true

echo "==[2] ensure feature dir =="
mkdir -p /root/royal_bot/royal_bot/features

echo "==[3] move old zh_alias if it was created in wrong place =="
# 你之前把 zh_alias.py 放到了 /root/royal_bot/features/ 不是包目录，会导致 ModuleNotFoundError
if [ -f /root/royal_bot/features/zh_alias.py ]; then
  cp -a /root/royal_bot/features/zh_alias.py /root/royal_bot/royal_bot/features/zh_alias.py
fi
if [ -f /root/royal_bot/zh_alias.json ]; then
  cp -a /root/royal_bot/zh_alias.json /root/royal_bot/royal_bot/features/zh_alias.json
fi

echo "==[4] backup files =="
for f in \
  /root/royal_bot/royal_bot/features/zh_alias.py \
  /root/royal_bot/royal_bot/features/bind_admin2.py \
  /root/royal_bot/royal_bot/features/binding.py
do
  [ -f "$f" ] && cp -a "$f" "$f.bak.$TS"
done

echo "==[5] write zh_alias (safe: no hijack /commands) =="
cat > /root/royal_bot/royal_bot/features/zh_alias.py <<'PY'
# -*- coding: utf-8 -*-
import json
import os
import logging
from pathlib import Path

from telegram.ext import MessageHandler, filters
from telegram.ext import CommandHandler

log = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
MAP_FILE = HERE / "zh_alias.json"

DEFAULT_MAP = {
  "菜单": "menu",
  "帮助": "menu",
  "我的": "me",
  "资料": "me",
  "签到": "daily",
  "打卡": "daily",
  "绑定": "bind",
  "审核": "requests",
  "申请": "requests",
  "海报": "poster",
  "墙": "wall",
  "转盘": "spin",
  "商店": "shop",
  "周榜": "bounty",
  "榜单": "bounty",
}

def _load_map():
  if MAP_FILE.exists():
    try:
      return json.loads(MAP_FILE.read_text(encoding="utf-8"))
    except Exception:
      log.exception("zh_alias.json 解析失败，使用默认映射")
  # 自动生成一份默认映射，方便你以后改
  try:
    MAP_FILE.write_text(json.dumps(DEFAULT_MAP, ensure_ascii=False, indent=2), encoding="utf-8")
  except Exception:
    pass
  return dict(DEFAULT_MAP)

ALIASES = _load_map()

def _find_cmd_handler(app, cmd: str):
  # 在所有 handler 里找 CommandHandler，然后直接调用 callback（不依赖 bot_command entities）
  for group, hs in (app.handlers or {}).items():
    for h in hs:
      if isinstance(h, CommandHandler):
        cmds = []
        if hasattr(h, "commands") and h.commands:
          cmds = list(h.commands)
        elif hasattr(h, "command") and h.command:
          cmds = [h.command] if isinstance(h.command, str) else list(h.command)
        if cmd in cmds:
          return h
  return None

async def _router(update, context):
  msg = update.effective_message
  if not msg or not msg.text:
    return

  text = msg.text.strip()
  # 只处理“非 / 命令”的纯中文输入，避免抢正常命令
  if text.startswith("/"):
    return

  # 支持 “绑定 yimaodidi” 这种带参数的中文
  first, *rest = text.split(maxsplit=1)
  cmd = ALIASES.get(first)
  if not cmd:
    return

  args = []
  if rest:
    args = rest[0].split()

  h = _find_cmd_handler(context.application, cmd)
  if not h:
    await msg.reply_text(f"⚠️ 我识别到你想执行「{first}」，但机器人没加载 /{cmd} 这个命令。")
    return

  # 给回调补上 args（CommandHandler 平时会做这个）
  try:
    context._args = args  # noqa
  except Exception:
    pass

  try:
    await h.callback(update, context)
  except Exception:
    log.exception("zh_alias dispatch failed: %s -> /%s %s", first, cmd, args)
    await msg.reply_text("⚠️ 中文指令已识别，但执行时异常了。我这边已经写日志了（看 journalctl）。")

def register(app, cfg):
  # 只处理 TEXT 且非 COMMAND，放到较后 group，绝不影响 /xxx
  app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _router), group=50)
  log.info("zh_alias loaded, map=%s", str(MAP_FILE))
PY

echo "==[6] write bind_admin2 (real buttons + robust approve/reject) =="
cat > /root/royal_bot/royal_bot/features/bind_admin2.py <<'PY'
# -*- coding: utf-8 -*-
import os
import sqlite3
import time
import logging
from typing import Dict, List, Tuple, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler

log = logging.getLogger(__name__)

def _cfg_get(cfg, key: str, default=None):
  if cfg is None:
    return os.getenv(key, default)
  if isinstance(cfg, dict):
    return cfg.get(key) or os.getenv(key, default)
  return getattr(cfg, key, None) or os.getenv(key, default)

def _db_path(cfg) -> str:
  return _cfg_get(cfg, "DB_FILE", "/root/royal_bot/royal_bot.db")

def _conn(db: str):
  c = sqlite3.connect(db)
  c.row_factory = sqlite3.Row
  return c

def _tables(c) -> List[str]:
  return [r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

def _cols(c, t: str) -> List[str]:
  return [r["name"] for r in c.execute(f"PRAGMA table_info({t})").fetchall()]

def _pick_request_table(c) -> Optional[str]:
  # 找“绑定申请表”：含 tg_id/user_id + emby + id
  cand = []
  for t in _tables(c):
    cols = _cols(c, t)
    low = [x.lower() for x in cols]
    if "id" in low and any(x in low for x in ["tg_id","telegram_id","user_id"]) and any(x in low for x in ["emby","emby_user","emby_username"]):
      if "request" in t.lower() or "bind" in t.lower():
        cand.append(t)
  return cand[0] if cand else None

def _pick_binding_tables(c) -> List[str]:
  # 找“绑定关系表”：含 tg_id/user_id + emby（排除明显 request 表）
  out = []
  for t in _tables(c):
    tl = t.lower()
    if "request" in tl:
      continue
    cols = _cols(c, t)
    low = [x.lower() for x in cols]
    if any(x in low for x in ["tg_id","telegram_id","user_id"]) and any(x in low for x in ["emby","emby_user","emby_username"]):
      out.append(t)
  return out

async def _tg_name(bot, uid: int) -> str:
  try:
    chat = await bot.get_chat(uid)
    if getattr(chat, "username", None):
      return f"@{chat.username}"
    name = " ".join([x for x in [getattr(chat, "first_name", None), getattr(chat, "last_name", None)] if x])
    return name or str(uid)
  except Exception:
    return str(uid)

def _kb(rid: int) -> InlineKeyboardMarkup:
  return InlineKeyboardMarkup([[
    InlineKeyboardButton("✅ 通过", callback_data=f"bind:approve:{rid}"),
    InlineKeyboardButton("❌ 拒绝", callback_data=f"bind:reject:{rid}")
  ]])

def _now() -> int:
  return int(time.time())

def _coerce_id(x: str) -> int:
  x = x.strip()
  if x.startswith("#"):
    x = x[1:]
  return int(x)

def _find_row_by_id(c, table: str, rid: int):
  cols = _cols(c, table)
  cset = {x.lower() for x in cols}
  # id 列名大概率就是 id
  return c.execute(f"SELECT * FROM {table} WHERE id=?", (rid,)).fetchone()

def _status_cols(cols: List[str]) -> Dict[str, str]:
  low = {x.lower(): x for x in cols}
  out = {}
  for k in ["status","state","approved","is_approved","approved_by","approved_at","updated_at","created_at","ts","time"]:
    if k in low:
      out[k] = low[k]
  return out

def _get_field(row, names: List[str]):
  for n in names:
    if n in row.keys():
      return row[n]
    ln = n.lower()
    for k in row.keys():
      if k.lower() == ln:
        return row[k]
  return None

def _upsert_binding(c, table: str, tg_id: int, emby: str):
  cols = _cols(c, table)
  low = [x.lower() for x in cols]
  tg_col = None
  emby_col = None
  for x in cols:
    xl = x.lower()
    if xl in ("tg_id","telegram_id","user_id"):
      tg_col = x
    if xl in ("emby","emby_user","emby_username"):
      emby_col = x
  if not tg_col or not emby_col:
    return

  # 其它可选字段
  extras = {}
  for x in cols:
    xl = x.lower()
    if xl in ("updated_at","ts","time") and x not in (tg_col, emby_col):
      extras[x] = _now()

  # 先尝试 update
  set_parts = [f"{emby_col}=?"] + [f"{k}=?" for k in extras.keys()]
  params = [emby] + list(extras.values()) + [tg_id]
  cur = c.execute(f"UPDATE {table} SET {', '.join(set_parts)} WHERE {tg_col}=?", params)
  if cur.rowcount and cur.rowcount > 0:
    return

  # 不存在则 insert（尽量填齐）
  insert_cols = [tg_col, emby_col] + list(extras.keys())
  insert_vals = [tg_id, emby] + list(extras.values())
  ph = ",".join(["?"] * len(insert_cols))
  c.execute(f"INSERT INTO {table} ({','.join(insert_cols)}) VALUES ({ph})", insert_vals)

def _mark_request(c, table: str, rid: int, action: str, admin_id: int):
  cols = _cols(c, table)
  sc = _status_cols(cols)

  # 如果有 status/state 字段就写状态；否则直接删（当作已处理）
  if "status" in sc:
    c.execute(f"UPDATE {table} SET {sc['status']}=? WHERE id=?", (action, rid))
  elif "state" in sc:
    c.execute(f"UPDATE {table} SET {sc['state']}=? WHERE id=?", (action, rid))
  elif "approved" in sc:
    c.execute(f"UPDATE {table} SET {sc['approved']}=? WHERE id=?", (1 if action=="approved" else 0, rid))
  else:
    c.execute(f"DELETE FROM {table} WHERE id=?", (rid,))

  if "approved_by" in sc:
    c.execute(f"UPDATE {table} SET {sc['approved_by']}=? WHERE id=?", (admin_id, rid))
  if "approved_at" in sc:
    c.execute(f"UPDATE {table} SET {sc['approved_at']}=? WHERE id=?", (_now(), rid))

async def _do_action(update, context, action: str, rid: int):
  cfg = context.bot_data.get("__cfg__")
  db = _db_path(cfg)
  admin = update.effective_user.id
  with _conn(db) as c:
    req_table = _pick_request_table(c)
    if not req_table:
      await update.effective_message.reply_text("❌ 找不到绑定申请表（数据库里没识别出来）。")
      return

    row = _find_row_by_id(c, req_table, rid)
    if not row:
      await update.effective_message.reply_text(f"❌ 找不到这个申请号：#{rid}")
      return

    tg_id = int(_get_field(row, ["tg_id","telegram_id","user_id"]))
    emby = str(_get_field(row, ["emby","emby_user","emby_username"]))

    if action == "approved":
      # 写入所有可能的绑定表，保证 /me 能看到
      bts = _pick_binding_tables(c)
      if not bts:
        # 如果没有，至少不让你“通过了但不绑定”
        await update.effective_message.reply_text("❌ 找不到绑定关系表（数据库里没识别出来）。")
        return
      for t in bts:
        try:
          _upsert_binding(c, t, tg_id, emby)
        except Exception:
          log.exception("upsert failed table=%s", t)

      _mark_request(c, req_table, rid, "approved", admin)
      c.commit()

      await update.effective_message.reply_text(f"✅ 已通过绑定：#{rid}\nTG: {tg_id}\nEmby: {emby}")
      try:
        await context.bot.send_message(chat_id=tg_id, text=f"✅ 你的绑定申请已通过\nEmby: {emby}")
      except Exception:
        pass

    else:
      _mark_request(c, req_table, rid, "rejected", admin)
      c.commit()
      await update.effective_message.reply_text(f"✅ 已拒绝：#{rid}")
      try:
        await context.bot.send_message(chat_id=tg_id, text=f"❌ 你的绑定申请被拒绝\nEmby: {emby}")
      except Exception:
        pass

async def cmd_requests(update, context):
  cfg = context.bot_data.get("__cfg__")
  db = _db_path(cfg)
  with _conn(db) as c:
    req_table = _pick_request_table(c)
    if not req_table:
      await update.effective_message.reply_text("❌ 找不到绑定申请表（数据库里没识别出来）。")
      return

    cols = _cols(c, req_table)
    sc = _status_cols(cols)
    where = ""
    params = ()
    if "status" in sc:
      where = f"WHERE {sc['status']} IS NULL OR {sc['status']}='' OR {sc['status']}='pending' OR {sc['status']}='0'"
    elif "state" in sc:
      where = f"WHERE {sc['state']} IS NULL OR {sc['state']}='' OR {sc['state']}='pending' OR {sc['state']}='0'"

    rows = c.execute(f"SELECT * FROM {req_table} {where} ORDER BY id DESC LIMIT 20", params).fetchall()

  if not rows:
    await update.effective_message.reply_text("✅ 当前没有待审核的绑定申请。")
    return

  for r in rows[::-1]:
    rid = int(_get_field(r, ["id"]))
    tg_id = int(_get_field(r, ["tg_id","telegram_id","user_id"]))
    emby = str(_get_field(r, ["emby","emby_user","emby_username"]))
    name = await _tg_name(context.bot, tg_id)
    text = (
      "👑 Royal Bot | 绑定申请\n"
      f"• 申请号：#{rid}\n"
      f"• TG：{name} ({tg_id})\n"
      f"• Emby：{emby}\n"
    )
    await update.effective_message.reply_text(text, reply_markup=_kb(rid))

async def cmd_approve(update, context):
  if not context.args:
    await update.effective_message.reply_text("用法：/approve 申请号（例如 /approve 7）")
    return
  rid = _coerce_id(context.args[0])
  await _do_action(update, context, "approved", rid)

async def cmd_reject(update, context):
  if not context.args:
    await update.effective_message.reply_text("用法：/reject 申请号（例如 /reject 7）")
    return
  rid = _coerce_id(context.args[0])
  await _do_action(update, context, "rejected", rid)

async def cb_bind(update, context):
  q = update.callback_query
  await q.answer()
  try:
    _, act, rid = q.data.split(":", 2)
    rid = int(rid)
  except Exception:
    return
  await _do_action(update, context, "approved" if act=="approve" else "rejected", rid)

def register(app, cfg):
  # 保存 cfg 方便读 DB_FILE
  app.bot_data["__cfg__"] = cfg

  # 用更高优先级接管 approve/reject/requests（避免旧逻辑失效）
  app.add_handler(CommandHandler("requests", cmd_requests), group=-10)
  app.add_handler(CommandHandler("approve", cmd_approve), group=-10)
  app.add_handler(CommandHandler("reject", cmd_reject), group=-10)
  app.add_handler(CallbackQueryHandler(cb_bind, pattern=r"^bind:(approve|reject):\d+$"), group=-10)

  log.info("bind_admin2 loaded")
PY

echo "==[7] patch binding notify: add real buttons if possible =="
# 轻量补丁：如果 binding.py 里有 send_message(... GROUP_ID ...)，就尽量加 reply_markup
python3 - <<'PY'
import re
from pathlib import Path
p = Path("/root/royal_bot/royal_bot/features/binding.py")
if not p.exists():
    print("binding.py not found, skip")
    raise SystemExit(0)

s = p.read_text(encoding="utf-8", errors="ignore")
orig = s

# 确保 import InlineKeyboard
if "InlineKeyboardButton" not in s:
    s = s.replace("from telegram import", "from telegram import InlineKeyboardButton, InlineKeyboardMarkup,")
    if s == orig:
        # 找不到就加在顶部
        s = "from telegram import InlineKeyboardButton, InlineKeyboardMarkup\n" + s

# 注入一个小工具函数（幂等）
if "_bind_kb(" not in s:
    inject = """
def _bind_kb(rid: int):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ 通过", callback_data=f"bind:approve:{rid}"),
        InlineKeyboardButton("❌ 拒绝", callback_data=f"bind:reject:{rid}")
    ]])
"""
    # 放在文件靠前位置（找第一个空行后）
    m = re.search(r"\n\n", s)
    if m:
        s = s[:m.end()] + inject + s[m.end():]
    else:
        s = inject + "\n" + s

# 尝试给发到群/管理员的 send_message 加 reply_markup
# 目标：包含 cfg.GROUP_ID 或 GROUP_ID 的 send_message 调用
pattern = re.compile(r"(await\s+context\.bot\.send_message\((?:.|\n)*?\))", re.M)
def add_kb(m):
    block = m.group(1)
    if "reply_markup=" in block:
        return block
    # 尝试找到 rid 变量名（常见：req_id / request_id / rid）
    rid_var = None
    for v in ["req_id", "request_id", "rid", "reqid"]:
        if re.search(rf"\b{v}\b", block):
            rid_var = v
            break
    if not rid_var:
        # 没找到就不动，避免误伤
        return block
    # 在最后一个 ) 前插入
    return block[:-1] + f", reply_markup=_bind_kb({rid_var}))"

new_s = pattern.sub(add_kb, s)

if new_s != orig:
    p.write_text(new_s, encoding="utf-8")
    print("binding.py patched: added inline buttons where possible")
else:
    print("binding.py unchanged (no safe patch point found)")
PY

echo "==[8] ensure FEATURE_MODULES includes bind_admin2 + zh_alias =="
python3 - <<'PY'
import re, pathlib
p=pathlib.Path("/root/royal_bot/.env")
s=p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""
if "FEATURE_MODULES=" not in s:
    s += "\nFEATURE_MODULES=royal_bot.features.bind_admin2,royal_bot.features.zh_alias\n"
else:
    m=re.search(r'^FEATURE_MODULES=(.*)$', s, flags=re.M)
    mods=[x.strip() for x in m.group(1).split(',') if x.strip()]
    # 把这俩放最前面，保证接管逻辑
    for n in ["royal_bot.features.bind_admin2","royal_bot.features.zh_alias"][::-1]:
        if n in mods: mods.remove(n)
        mods.insert(0,n)
    s=re.sub(r'^FEATURE_MODULES=.*$', "FEATURE_MODULES="+",".join(mods), s, flags=re.M)
p.write_text(s, encoding="utf-8")
print("FEATURE_MODULES updated")
PY

echo "==[9] compile sanity =="
python3 -m py_compile \
  /root/royal_bot/royal_bot/features/zh_alias.py \
  /root/royal_bot/royal_bot/features/bind_admin2.py || (echo "py_compile failed" && exit 1)

echo "==[10] restart =="
systemctl daemon-reload || true
systemctl start tgbot
sleep 1
systemctl status tgbot --no-pager -l | sed -n '1,80p'

echo "==[DONE] 测试方法：私聊发「菜单」「绑定 yimaodidi」「审核」，点按钮通过/拒绝 =="
