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
