import os, sqlite3, datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, CallbackQueryHandler
from telegram.ext import ApplicationHandlerStop

DB_FILE = os.environ.get("DB_FILE", "/root/royal_bot/royal_bot.db")
BIND_REQUIRES_APPROVAL = int(os.environ.get("BIND_REQUIRES_APPROVAL", "1") or "1")
OWNER_ID = int(os.environ.get("OWNER_ID", "0") or "0")
GROUP_ID = int(os.environ.get("GROUP_ID", "0") or "0")

def _conn():
    return sqlite3.connect(DB_FILE)

def _tables(cur):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {r[0] for r in cur.fetchall()}

def _cols(cur, t):
    cur.execute(f"PRAGMA table_info({t})")
    return [r[1] for r in cur.fetchall()]

def _detect_req_table(cur):
    tables = _tables(cur)
    for t in ("bind_requests", "binding_requests", "bind_request", "binding_request"):
        if t in tables:
            return t
    # create default
    cur.execute("""CREATE TABLE IF NOT EXISTS bind_requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER NOT NULL,
        emby_name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT
    )""")
    return "bind_requests"

def _ensure_schema():
    con = _conn()
    cur = con.cursor()
    tables = _tables(cur)

    if "bindings" not in tables:
        cur.execute("""CREATE TABLE bindings(
            tg_id INTEGER PRIMARY KEY,
            emby_name TEXT
        )""")
    bcols = _cols(cur, "bindings")
    if "created_at" not in bcols:
        try:
            cur.execute("ALTER TABLE bindings ADD COLUMN created_at TEXT")
        except Exception:
            pass

    req_table = _detect_req_table(cur)
    rcols = _cols(cur, req_table)
    if "status" not in rcols:
        try:
            cur.execute(f"ALTER TABLE {req_table} ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'")
        except Exception:
            pass
    if "created_at" not in rcols:
        try:
            cur.execute(f"ALTER TABLE {req_table} ADD COLUMN created_at TEXT")
        except Exception:
            pass

    con.commit()
    con.close()

def _upsert_binding(tg_id: int, emby_name: str):
    con = _conn()
    cur = con.cursor()
    _ensure_schema()
    cols = _cols(cur, "bindings")
    now = datetime.datetime.utcnow().isoformat(timespec="seconds")

    # build dynamic insert/update
    if "tg_id" in cols and "emby_name" in cols:
        if "created_at" in cols:
            cur.execute(
                "INSERT INTO bindings(tg_id, emby_name, created_at) VALUES(?,?,?) "
                "ON CONFLICT(tg_id) DO UPDATE SET emby_name=excluded.emby_name",
                (tg_id, emby_name, now)
            )
        else:
            cur.execute(
                "INSERT INTO bindings(tg_id, emby_name) VALUES(?,?) "
                "ON CONFLICT(tg_id) DO UPDATE SET emby_name=excluded.emby_name",
                (tg_id, emby_name)
            )
    con.commit()
    con.close()

def _create_request(tg_id: int, emby_name: str) -> int:
    con = _conn()
    cur = con.cursor()
    _ensure_schema()
    rt = _detect_req_table(cur)
    cols = _cols(cur, rt)
    now = datetime.datetime.utcnow().isoformat(timespec="seconds")

    if "created_at" in cols:
        cur.execute(f"INSERT INTO {rt}(tg_id, emby_name, status, created_at) VALUES(?,?,?,?)",
                    (tg_id, emby_name, "pending", now))
    else:
        cur.execute(f"INSERT INTO {rt}(tg_id, emby_name, status) VALUES(?,?,?)",
                    (tg_id, emby_name, "pending"))
    rid = cur.lastrowid
    con.commit()
    con.close()
    return rid

def _get_pending():
    con = _conn()
    cur = con.cursor()
    _ensure_schema()
    rt = _detect_req_table(cur)
    cols = _cols(cur, rt)

    # status field might not exist in some legacy, but we ensure it
    if "created_at" in cols:
        cur.execute(f"SELECT id, tg_id, emby_name, created_at FROM {rt} WHERE status='pending' ORDER BY id DESC")
        rows = cur.fetchall()
        con.close()
        return rows
    else:
        cur.execute(f"SELECT id, tg_id, emby_name FROM {rt} WHERE status='pending' ORDER BY id DESC")
        rows = cur.fetchall()
        con.close()
        return [(r[0], r[1], r[2], None) for r in rows]

def _set_request_status(rid: int, status: str):
    con = _conn()
    cur = con.cursor()
    _ensure_schema()
    rt = _detect_req_table(cur)
    cur.execute(f"UPDATE {rt} SET status=? WHERE id=?", (status, rid))
    con.commit()
    con.close()

def _kb(rid: int):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ 通过", callback_data=f"bind:approve:{rid}"),
        InlineKeyboardButton("❌ 拒绝", callback_data=f"bind:reject:{rid}")
    ]])

async def cmd_bind(update, context):
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user:
        return

    args = context.args or []
    if not args:
        await msg.reply_text("用法：/bind <Emby用户名>\n例如：/bind yimaodidi")
        raise ApplicationHandlerStop

    emby_name = args[0].strip()
    if not emby_name:
        await msg.reply_text("Emby 用户名不能为空。")
        raise ApplicationHandlerStop

    if BIND_REQUIRES_APPROVAL:
        rid = _create_request(user.id, emby_name)
        await msg.reply_text(f"📝 已提交绑定申请（#{rid}）\nEmby：{emby_name}\n⏳ 等管理员审核通过就生效~")

        # notify: same chat + optional owner/group
        text = (
            f"👑 Royal Bot | 绑定申请\n"
            f"• 申请号：#{rid}\n"
            f"• TG：{user.full_name} ({user.id})\n"
            f"• Emby：{emby_name}\n"
        )
        # send to current chat
        try:
            await context.bot.send_message(chat_id=msg.chat_id, text=text, reply_markup=_kb(rid))
        except Exception:
            pass
        # send to owner (only works if owner has started bot)
        if OWNER_ID:
            try:
                await context.bot.send_message(chat_id=OWNER_ID, text=text, reply_markup=_kb(rid))
            except Exception:
                pass
        # send to group if configured and not already in that group
        if GROUP_ID and GROUP_ID != msg.chat_id:
            try:
                await context.bot.send_message(chat_id=GROUP_ID, text=text, reply_markup=_kb(rid))
            except Exception:
                pass
    else:
        _upsert_binding(user.id, emby_name)
        await msg.reply_text(f"✅ 绑定成功：{emby_name}")

    raise ApplicationHandlerStop

async def cmd_requests(update, context):
    msg = update.effective_message
    rows = _get_pending()
    if not rows:
        await msg.reply_text("💤 当前没有待审核绑定申请。")
        raise ApplicationHandlerStop

    # send one card per request with real buttons
    for rid, tg_id, emby_name, created_at in rows[:20]:
        ts = f"\n• 时间：{created_at}" if created_at else ""
        text = f"💗 待审核绑定申请\n• 申请号：#{rid}\n• TG：{tg_id}\n• Emby：{emby_name}{ts}"
        await msg.reply_text(text, reply_markup=_kb(rid))
    raise ApplicationHandlerStop

async def _do_approve(update, context, rid: int):
    # find request info
    con = _conn()
    cur = con.cursor()
    _ensure_schema()
    rt = _detect_req_table(cur)
    cur.execute(f"SELECT tg_id, emby_name, status FROM {rt} WHERE id=?", (rid,))
    row = cur.fetchone()
    con.close()

    if not row:
        await update.effective_message.reply_text("找不到这个申请号～")
        return
    tg_id, emby_name, status = row
    if status != "pending":
        await update.effective_message.reply_text(f"这个申请已处理：{status}")
        return

    _set_request_status(rid, "approved")
    _upsert_binding(int(tg_id), str(emby_name))

    # notify
    await update.effective_message.reply_text(f"✅ 已通过申请 #{rid}，绑定生效：{emby_name}")
    try:
        await context.bot.send_message(chat_id=int(tg_id), text=f"✅ 你的绑定申请 #{rid} 已通过：{emby_name}")
    except Exception:
        pass

async def _do_reject(update, context, rid: int):
    con = _conn()
    cur = con.cursor()
    _ensure_schema()
    rt = _detect_req_table(cur)
    cur.execute(f"SELECT tg_id, emby_name, status FROM {rt} WHERE id=?", (rid,))
    row = cur.fetchone()
    con.close()

    if not row:
        await update.effective_message.reply_text("找不到这个申请号～")
        return
    tg_id, emby_name, status = row
    if status != "pending":
        await update.effective_message.reply_text(f"这个申请已处理：{status}")
        return

    _set_request_status(rid, "rejected")
    await update.effective_message.reply_text(f"❌ 已拒绝申请 #{rid}")
    try:
        await context.bot.send_message(chat_id=int(tg_id), text=f"❌ 你的绑定申请 #{rid} 已被拒绝：{emby_name}")
    except Exception:
        pass

async def cmd_approve(update, context):
    msg = update.effective_message
    if not context.args:
        await msg.reply_text("用法：/approve 申请号")
        raise ApplicationHandlerStop
    rid = int(str(context.args[0]).lstrip("#"))
    await _do_approve(update, context, rid)
    raise ApplicationHandlerStop

async def cmd_reject(update, context):
    msg = update.effective_message
    if not context.args:
        await msg.reply_text("用法：/reject 申请号")
        raise ApplicationHandlerStop
    rid = int(str(context.args[0]).lstrip("#"))
    await _do_reject(update, context, rid)
    raise ApplicationHandlerStop

async def cb_bind(update, context):
    q = update.callback_query
    if not q or not q.data:
        return
    await q.answer()
    try:
        _, action, rid_s = q.data.split(":", 2)
        rid = int(rid_s)
    except Exception:
        return

    if action == "approve":
        await _do_approve(update, context, rid)
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
    elif action == "reject":
        await _do_reject(update, context, rid)
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

def register(app, cfg):
    _ensure_schema()
    # Put our handlers very early so old/broken ones won't interfere
    app.add_handler(CommandHandler("bind", cmd_bind), group=-999)
    app.add_handler(CommandHandler("requests", cmd_requests), group=-999)
    app.add_handler(CommandHandler("approve", cmd_approve), group=-999)
    app.add_handler(CommandHandler("reject", cmd_reject), group=-999)
    app.add_handler(CallbackQueryHandler(cb_bind, pattern=r"^bind:(approve|reject):\d+$"), group=-999)
