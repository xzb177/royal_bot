set -euo pipefail
cd /root/royal_bot
TS="$(date +%Y%m%d-%H%M%S)"

echo "== stop bot =="
systemctl stop tgbot || true

TARGET="/root/royal_bot/royal_bot/features/binding.py"
if [ ! -f "$TARGET" ]; then
  echo "❌ 找不到 $TARGET"
  exit 1
fi

echo "== backup =="
cp -a "$TARGET" "$TARGET.bak.$TS"

echo "== patch binding.py (DB columns auto-detect + real buttons + stop old handlers) =="
python3 - <<'PY'
import re
from pathlib import Path

p = Path("/root/royal_bot/royal_bot/features/binding.py")
s = p.read_text(encoding="utf-8", errors="ignore")

# 1) 确保必要 import（不重复）
need_imports = [
    "import os",
    "import sqlite3",
    "import time",
    "import logging",
]
for imp in need_imports:
    if imp not in s:
        s = imp + "\n" + s

# telegram imports
if "InlineKeyboardButton" not in s or "InlineKeyboardMarkup" not in s:
    # 尽量不破坏原有 import，直接追加
    s = s.replace("from telegram import", "from telegram import InlineKeyboardButton, InlineKeyboardMarkup,")
    if "InlineKeyboardButton" not in s:
        s = "from telegram import InlineKeyboardButton, InlineKeyboardMarkup\n" + s

if "ApplicationHandlerStop" not in s:
    # v20+ 里用这个阻断后续 handler
    if "from telegram.ext import" in s:
        s = s.replace("from telegram.ext import", "from telegram.ext import ApplicationHandlerStop,")
    else:
        s = "from telegram.ext import ApplicationHandlerStop\n" + s

# 2) 追加“强制修复版”的审核/通过/拒绝/按钮逻辑（独立，不依赖原函数）
if "### BEGIN BINDINGS HOTFIX ###" not in s:
    hotfix = r'''
### BEGIN BINDINGS HOTFIX ###
log = logging.getLogger(__name__)

def _db_path(cfg=None):
    # 优先 cfg.DB_FILE / cfg["DB_FILE"]，否则 env DB_FILE，否则默认
    try:
        if isinstance(cfg, dict) and cfg.get("DB_FILE"):
            return cfg["DB_FILE"]
        if hasattr(cfg, "DB_FILE") and getattr(cfg, "DB_FILE"):
            return getattr(cfg, "DB_FILE")
    except Exception:
        pass
    return os.getenv("DB_FILE", "/root/royal_bot/royal_bot.db")

def _conn(db):
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    return c

def _tables(c):
    return [r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

def _cols(c, t):
    return [r["name"] for r in c.execute(f"PRAGMA table_info({t})").fetchall()]

def _pick_req_table(c):
    # 绑定申请表：有 id + tg_id/user_id + emby
    cand = []
    for t in _tables(c):
        cols = _cols(c, t)
        low = [x.lower() for x in cols]
        if "id" in low and any(x in low for x in ["tg_id","telegram_id","user_id"]) and any(x in low for x in ["emby","emby_user","emby_username","emby_name"]):
            if "request" in t.lower() or "bind" in t.lower():
                cand.append(t)
    return cand[0] if cand else None

def _pick_bind_table(c):
    # 绑定关系表：优先就叫 bindings，其次找含 tg_id + emby 的表
    if "bindings" in _tables(c):
        return "bindings"
    for t in _tables(c):
        if "request" in t.lower():
            continue
        cols = _cols(c, t)
        low = [x.lower() for x in cols]
        if any(x in low for x in ["tg_id","telegram_id","user_id"]) and any(x in low for x in ["emby","emby_user","emby_username","emby_name"]):
            return t
    return None

def _get(row, names):
    if row is None: 
        return None
    keys = list(row.keys())
    lk = {k.lower(): k for k in keys}
    for n in names:
        k = lk.get(n.lower())
        if k:
            return row[k]
    return None

def _now():
    return int(time.time())

def _bind_kb(rid:int):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ 通过", callback_data=f"bind:approve:{rid}"),
        InlineKeyboardButton("❌ 拒绝", callback_data=f"bind:reject:{rid}")
    ]])

def _upsert_binding(c, table, tg_id:int, emby:str):
    cols = _cols(c, table)
    low = [x.lower() for x in cols]
    tg_col = None
    emby_col = None
    for x in cols:
        xl = x.lower()
        if xl in ("tg_id","telegram_id","user_id"):
            tg_col = x
        if xl in ("emby","emby_user","emby_username","emby_name"):
            emby_col = x
    if not tg_col or not emby_col:
        raise RuntimeError("binding table missing columns")

    extra = {}
    for x in cols:
        xl = x.lower()
        if xl in ("updated_at","ts","time") and x not in (tg_col, emby_col):
            extra[x] = _now()
        # 注意：绝对不要强塞 created_at（你就是死在这）
        # 如果表里有 created_at，我们也可以在 insert 时写；update 不写
    # 先 update
    set_parts = [f"{emby_col}=?"] + [f"{k}=?" for k in extra.keys()]
    params = [emby] + list(extra.values()) + [tg_id]
    cur = c.execute(f"UPDATE {table} SET {', '.join(set_parts)} WHERE {tg_col}=?", params)
    if cur.rowcount and cur.rowcount > 0:
        return

    # insert：只写实际存在的列
    ins_cols = [tg_col, emby_col] + list(extra.keys())
    ins_vals = [tg_id, emby] + list(extra.values())
    # 如果表里确实有 created_at，就补上
    if "created_at" in low:
        ca = cols[low.index("created_at")]
        ins_cols.append(ca)
        ins_vals.append(_now())

    ph = ",".join(["?"] * len(ins_cols))
    c.execute(f"INSERT INTO {table} ({','.join(ins_cols)}) VALUES ({ph})", ins_vals)

def _mark_req(c, table, rid:int, status:str, admin_id:int):
    cols = _cols(c, table)
    low = [x.lower() for x in cols]
    # 常见字段名兼容
    status_col = None
    for cand in ("status","state","approved","is_approved"):
        if cand in low:
            status_col = cols[low.index(cand)]
            break
    if status_col:
        if status_col.lower() in ("approved","is_approved"):
            c.execute(f"UPDATE {table} SET {status_col}=? WHERE id=?", (1 if status=="approved" else 0, rid))
        else:
            c.execute(f"UPDATE {table} SET {status_col}=? WHERE id=?", (status, rid))
    else:
        # 没状态列就直接删掉，表示已处理
        c.execute(f"DELETE FROM {table} WHERE id=?", (rid,))

    if "approved_by" in low:
        c.execute(f"UPDATE {table} SET {cols[low.index('approved_by')]}=? WHERE id=?", (admin_id, rid))
    if "approved_at" in low:
        c.execute(f"UPDATE {table} SET {cols[low.index('approved_at')]}=? WHERE id=?", (_now(), rid))

def _coerce_id(x:str)->int:
    x=x.strip()
    if x.startswith("#"): x=x[1:]
    return int(x)

async def _hotfix_requests(update, context):
    cfg = context.bot_data.get("__cfg__")
    db = _db_path(cfg)
    with _conn(db) as c:
        rt = _pick_req_table(c)
        if not rt:
            await update.effective_message.reply_text("❌ 找不到绑定申请表（没识别出来）。")
            raise ApplicationHandlerStop

        cols = _cols(c, rt)
        low = [x.lower() for x in cols]
        status_col = None
        for cand in ("status","state"):
            if cand in low:
                status_col = cols[low.index(cand)]
                break
        where = ""
        if status_col:
            where = f"WHERE {status_col} IS NULL OR {status_col}='' OR {status_col}='pending' OR {status_col}='0'"
        rows = c.execute(f"SELECT * FROM {rt} {where} ORDER BY id DESC LIMIT 20").fetchall()

    if not rows:
        await update.effective_message.reply_text("✅ 当前没有待审核绑定申请。")
        raise ApplicationHandlerStop

    for r in rows[::-1]:
        rid = int(_get(r, ["id"]))
        tg_id = int(_get(r, ["tg_id","telegram_id","user_id"]))
        emby = str(_get(r, ["emby","emby_user","emby_username","emby_name"]))
        text = (
            "👑 Royal Bot | 绑定申请\n"
            f"• 申请号：#{rid}\n"
            f"• TG：{tg_id}\n"
            f"• Emby：{emby}\n"
        )
        await update.effective_message.reply_text(text, reply_markup=_bind_kb(rid))
    raise ApplicationHandlerStop

async def _hotfix_approve(update, context):
    if not context.args:
        await update.effective_message.reply_text("用法：/approve 申请号（例如 /approve 7）")
        raise ApplicationHandlerStop
    rid = _coerce_id(context.args[0])

    cfg = context.bot_data.get("__cfg__")
    db = _db_path(cfg)
    admin = update.effective_user.id

    with _conn(db) as c:
        rt = _pick_req_table(c)
        bt = _pick_bind_table(c)
        if not rt or not bt:
            await update.effective_message.reply_text("❌ 数据库表识别失败（申请表/绑定表）。")
            raise ApplicationHandlerStop
        row = c.execute(f"SELECT * FROM {rt} WHERE id=?", (rid,)).fetchone()
        if not row:
            await update.effective_message.reply_text(f"❌ 找不到这个申请号：#{rid}")
            raise ApplicationHandlerStop

        tg_id = int(_get(row, ["tg_id","telegram_id","user_id"]))
        emby = str(_get(row, ["emby","emby_user","emby_username","emby_name"]))

        _upsert_binding(c, bt, tg_id, emby)
        _mark_req(c, rt, rid, "approved", admin)
        c.commit()

    await update.effective_message.reply_text(f"✅ 已通过：#{rid}\nTG: {tg_id}\nEmby: {emby}")
    try:
        await context.bot.send_message(chat_id=tg_id, text=f"✅ 你的绑定已通过\nEmby: {emby}")
    except Exception:
        pass
    raise ApplicationHandlerStop

async def _hotfix_reject(update, context):
    if not context.args:
        await update.effective_message.reply_text("用法：/reject 申请号（例如 /reject 7）")
        raise ApplicationHandlerStop
    rid = _coerce_id(context.args[0])

    cfg = context.bot_data.get("__cfg__")
    db = _db_path(cfg)
    admin = update.effective_user.id

    with _conn(db) as c:
        rt = _pick_req_table(c)
        if not rt:
            await update.effective_message.reply_text("❌ 找不到绑定申请表。")
            raise ApplicationHandlerStop
        row = c.execute(f"SELECT * FROM {rt} WHERE id=?", (rid,)).fetchone()
        if not row:
            await update.effective_message.reply_text(f"❌ 找不到这个申请号：#{rid}")
            raise ApplicationHandlerStop

        tg_id = int(_get(row, ["tg_id","telegram_id","user_id"]))
        emby = str(_get(row, ["emby","emby_user","emby_username","emby_name"]))

        _mark_req(c, rt, rid, "rejected", admin)
        c.commit()

    await update.effective_message.reply_text(f"✅ 已拒绝：#{rid}")
    try:
        await context.bot.send_message(chat_id=tg_id, text=f"❌ 你的绑定申请被拒绝\nEmby: {emby}")
    except Exception:
        pass
    raise ApplicationHandlerStop

async def _hotfix_cb(update, context):
    q = update.callback_query
    await q.answer()
    try:
        _, act, rid = q.data.split(":", 2)
        rid = int(rid)
    except Exception:
        raise ApplicationHandlerStop

    class FakeArgs:
        args = [str(rid)]
    # 复用命令逻辑
    if act == "approve":
        context.args = [str(rid)]
        await _hotfix_approve(update, context)
    else:
        context.args = [str(rid)]
        await _hotfix_reject(update, context)
    raise ApplicationHandlerStop
### END BINDINGS HOTFIX ###
'''
    s += "\n" + hotfix

# 3) 把 hotfix handlers 注入 register() 顶部（保证先接管并阻断旧逻辑）
m = re.search(r"^def\s+register\s*\(\s*app\s*,\s*cfg\s*\)\s*:\s*$", s, flags=re.M)
if not m:
    raise SystemExit("❌ 没找到 def register(app, cfg): 无法自动注入")
# 找到 register 函数体开始位置（下一行缩进）
start = m.end()
# 插入点：register 下一行
inject = """
    # --- HOTFIX: override approve/reject/requests + inline buttons ---
    app.bot_data["__cfg__"] = cfg
    try:
        app.add_handler(CommandHandler("requests", _hotfix_requests), group=-999)
        app.add_handler(CommandHandler("approve", _hotfix_approve), group=-999)
        app.add_handler(CommandHandler("reject", _hotfix_reject), group=-999)
        app.add_handler(CallbackQueryHandler(_hotfix_cb, pattern=r"^bind:(approve|reject):\\d+$"), group=-999)
    except Exception:
        log.exception("HOTFIX register failed")
    # --- end hotfix ---
"""
# 需要 CommandHandler/CallbackQueryHandler 可用
if "CallbackQueryHandler" not in s:
    if "from telegram.ext import" in s:
        s = s.replace("from telegram.ext import", "from telegram.ext import CallbackQueryHandler, CommandHandler,")
    else:
        s = "from telegram.ext import CallbackQueryHandler, CommandHandler\n" + s

# 注入（防重复）
if "HOTFIX: override approve/reject/requests" not in s:
    # 在 register 定义行后面插入
    lines = s.splitlines(True)
    # 找到 def register 行号
    idx = None
    for i, line in enumerate(lines):
        if re.match(r"^def\s+register\s*\(\s*app\s*,\s*cfg\s*\)\s*:\s*$", line):
            idx = i
            break
    if idx is None:
        raise SystemExit("inject failed")
    lines.insert(idx+1, inject)
    s = "".join(lines)

p.write_text(s, encoding="utf-8")
print("patched ok")
PY

echo "== py_compile =="
python3 -m py_compile /root/royal_bot/royal_bot/features/binding.py

echo "== restart =="
systemctl start tgbot
sleep 1
systemctl status tgbot --no-pager -l | sed -n '1,70p'

echo "== DONE =="
echo "测试：/requests 看是否带按钮；点按钮 或 /approve 7；再让用户 /me 看绑定状态"
