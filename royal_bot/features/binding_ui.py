# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def _connect(db_file: str):
    conn = sqlite3.connect(db_file, timeout=30)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    # reduce "database is locked"
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("PRAGMA busy_timeout=30000;")
    return conn

def _ensure_schema(conn: sqlite3.Connection):
    cur = conn.cursor()

    # requests table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bind_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER NOT NULL,
        tg_username TEXT,
        tg_name TEXT,
        emby_name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,
        decided_at TEXT
    );
    """)

    # bindings table (try to match /me expectation: tg_id + emby_name)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bindings (
        tg_id INTEGER PRIMARY KEY,
        emby_name TEXT NOT NULL,
        created_at TEXT
    );
    """)

    # add missing cols if older schema exists
    def addcol(table, col, ddl):
        cols = {r["name"] for r in cur.execute(f"PRAGMA table_info({table});").fetchall()}
        if col not in cols:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {ddl};")

    addcol("bindings", "created_at", "created_at TEXT")
    addcol("bindings", "tg_username", "tg_username TEXT")
    addcol("bindings", "tg_name", "tg_name TEXT")
    addcol("bindings", "updated_at", "updated_at TEXT")

    conn.commit()

async def _is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, cfg) -> bool:
    uid = update.effective_user.id if update.effective_user else None
    if uid is None:
        return False
    if getattr(cfg, "OWNER_ID", None) and uid == int(cfg.OWNER_ID):
        return True

    # also allow chat admins in the current chat
    try:
        chat = update.effective_chat
        if chat:
            m = await context.bot.get_chat_member(chat.id, uid)
            return m.status in ("administrator", "creator")
    except Exception:
        return False
    return False

def _kb(req_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ 通过", callback_data=f"bind:approve:{req_id}"),
            InlineKeyboardButton("❌ 拒绝", callback_data=f"bind:reject:{req_id}"),
        ]
    ])

def _admin_chat_id(cfg):
    # prefer GROUP_ID for审核通知
    gid = getattr(cfg, "GROUP_ID", None)
    if gid is not None:
        try:
            gid = int(gid)
            if gid != 0:
                return gid
        except Exception:
            pass
    # fallback owner
    oid = getattr(cfg, "OWNER_ID", None)
    if oid is not None:
        try:
            return int(oid)
        except Exception:
            pass
    return None

async def cmd_bind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = context.application.bot_data.get("__cfg__")
    db_file = getattr(cfg, "DB_FILE", "/root/royal_bot/royal_bot.db")

    if not context.args:
        await update.message.reply_text("用法：/bind <Emby用户名>\n例如：/bind yimaodidi")
        raise ApplicationHandlerStop()

    emby_name = " ".join(context.args).strip()
    u = update.effective_user
    tg_id = u.id
    tg_username = (u.username or "").strip() or None
    tg_name = (u.full_name or "").strip() or None

    conn = _connect(db_file)
    try:
        _ensure_schema(conn)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO bind_requests (tg_id, tg_username, tg_name, emby_name, status, created_at) VALUES (?,?,?,?,?,?)",
            (tg_id, tg_username, tg_name, emby_name, "pending", _utc_now()),
        )
        req_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    # approval?
    need_approval = int(getattr(cfg, "BIND_REQUIRES_APPROVAL", 1))
    if need_approval == 0:
        await _set_binding(context, cfg, tg_id, tg_username, tg_name, emby_name)
        await update.message.reply_text(f"✅ 绑定成功：{emby_name}")
        raise ApplicationHandlerStop()

    await update.message.reply_text(f"📝 已提交绑定申请（#{req_id}）\n⏳ 等管理员审核通过就生效～")

    admin_chat = _admin_chat_id(cfg)
    if admin_chat:
        text = (
            f"👑 Royal Bot | 绑定申请\n"
            f"• 申请号：#{req_id}\n"
            f"• TG：{(tg_username and '@'+tg_username) or (tg_name or '')} ({tg_id})\n"
            f"• Emby：{emby_name}\n"
        )
        try:
            await context.bot.send_message(chat_id=admin_chat, text=text, reply_markup=_kb(req_id))
        except Exception:
            # don't fail user flow
            pass

    raise ApplicationHandlerStop()

async def _set_binding(context: ContextTypes.DEFAULT_TYPE, cfg, tg_id: int, tg_username, tg_name, emby_name: str):
    db_file = getattr(cfg, "DB_FILE", "/root/royal_bot/royal_bot.db")
    conn = _connect(db_file)
    try:
        _ensure_schema(conn)
        cur = conn.cursor()

        cols = {r["name"] for r in cur.execute("PRAGMA table_info(bindings);").fetchall()}
        # upsert
        now = _utc_now()
        if "updated_at" in cols:
            cur.execute("""
                INSERT INTO bindings (tg_id, emby_name, tg_username, tg_name, created_at, updated_at)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(tg_id) DO UPDATE SET
                    emby_name=excluded.emby_name,
                    tg_username=excluded.tg_username,
                    tg_name=excluded.tg_name,
                    updated_at=excluded.updated_at
            """, (tg_id, emby_name, tg_username, tg_name, now, now))
        else:
            cur.execute("""
                INSERT INTO bindings (tg_id, emby_name, created_at)
                VALUES (?,?,?)
                ON CONFLICT(tg_id) DO UPDATE SET emby_name=excluded.emby_name
            """, (tg_id, emby_name, now))

        conn.commit()
    finally:
        conn.close()

async def _decide(context: ContextTypes.DEFAULT_TYPE, cfg, req_id: int, approve: bool):
    db_file = getattr(cfg, "DB_FILE", "/root/royal_bot/royal_bot.db")
    conn = _connect(db_file)
    row = None
    try:
        _ensure_schema(conn)
        cur = conn.cursor()
        row = cur.execute("SELECT * FROM bind_requests WHERE id=?", (req_id,)).fetchone()
        if not row:
            return None, "not_found"

        if row["status"] != "pending":
            return row, "already_done"

        new_status = "approved" if approve else "rejected"
        cur.execute("UPDATE bind_requests SET status=?, decided_at=? WHERE id=?", (new_status, _utc_now(), req_id))
        conn.commit()
    finally:
        conn.close()

    if approve:
        await _set_binding(
            context, cfg,
            int(row["tg_id"]),
            row["tg_username"],
            row["tg_name"],
            row["emby_name"],
        )
        # notify user
        try:
            await context.bot.send_message(chat_id=int(row["tg_id"]), text=f"✅ 你的绑定申请 #{req_id} 已通过\nEmby：{row['emby_name']}")
        except Exception:
            pass
    else:
        try:
            await context.bot.send_message(chat_id=int(row["tg_id"]), text=f"❌ 你的绑定申请 #{req_id} 已被拒绝")
        except Exception:
            pass

    return row, "ok"

async def cmd_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = context.application.bot_data.get("__cfg__")
    if not await _is_admin(update, context, cfg):
        await update.message.reply_text("⛔️ 你不是管理员，不能查看待审核列表。")
        raise ApplicationHandlerStop()

    db_file = getattr(cfg, "DB_FILE", "/root/royal_bot/royal_bot.db")
    conn = _connect(db_file)
    try:
        _ensure_schema(conn)
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT * FROM bind_requests WHERE status='pending' ORDER BY id DESC LIMIT 30"
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        await update.message.reply_text("✅ 当前没有待审核绑定申请。")
        raise ApplicationHandlerStop()

    # one message per request (so each has its own buttons)
    for r in rows:
        tg_disp = (r["tg_username"] and "@"+r["tg_username"]) or (r["tg_name"] or "")
        text = (
            f"👑 Royal Bot | 绑定申请\n"
            f"• 申请号：#{r['id']}\n"
            f"• TG：{tg_disp} ({r['tg_id']})\n"
            f"• Emby：{r['emby_name']}\n"
            f"• 时间：{r['created_at']}\n"
        )
        await update.message.reply_text(text, reply_markup=_kb(int(r["id"])))

    raise ApplicationHandlerStop()

async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = context.application.bot_data.get("__cfg__")
    if not await _is_admin(update, context, cfg):
        await update.message.reply_text("⛔️ 你不是管理员，不能审批。")
        raise ApplicationHandlerStop()

    if not context.args or not str(context.args[0]).isdigit():
        await update.message.reply_text("用法：/approve 申请号\n例如：/approve 7")
        raise ApplicationHandlerStop()

    req_id = int(context.args[0])
    row, st = await _decide(context, cfg, req_id, True)
    if st == "not_found":
        await update.message.reply_text("找不到这个申请号～")
    elif st == "already_done":
        await update.message.reply_text(f"这个申请（#{req_id}）之前已经处理过了（{row['status']}）")
    else:
        await update.message.reply_text(f"✅ 已通过绑定申请 #{req_id}")
    raise ApplicationHandlerStop()

async def cmd_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = context.application.bot_data.get("__cfg__")
    if not await _is_admin(update, context, cfg):
        await update.message.reply_text("⛔️ 你不是管理员，不能审批。")
        raise ApplicationHandlerStop()

    if not context.args or not str(context.args[0]).isdigit():
        await update.message.reply_text("用法：/reject 申请号\n例如：/reject 7")
        raise ApplicationHandlerStop()

    req_id = int(context.args[0])
    row, st = await _decide(context, cfg, req_id, False)
    if st == "not_found":
        await update.message.reply_text("找不到这个申请号～")
    elif st == "already_done":
        await update.message.reply_text(f"这个申请（#{req_id}）之前已经处理过了（{row['status']}）")
    else:
        await update.message.reply_text(f"❌ 已拒绝绑定申请 #{req_id}")
    raise ApplicationHandlerStop()

async def cb_bind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = context.application.bot_data.get("__cfg__")
    q = update.callback_query
    await q.answer()

    if not await _is_admin(update, context, cfg):
        await q.answer("你不是管理员", show_alert=True)
        raise ApplicationHandlerStop()

    data = q.data or ""
    # bind:approve:7
    try:
        _, action, sid = data.split(":", 2)
        req_id = int(sid)
    except Exception:
        raise ApplicationHandlerStop()

    approve = (action == "approve")
    row, st = await _decide(context, cfg, req_id, approve)

    if st == "not_found":
        await q.edit_message_text("⚠️ 找不到这个申请号（可能已被清理）")
        raise ApplicationHandlerStop()
    if st == "already_done":
        await q.edit_message_text(f"ℹ️ 申请 #{req_id} 已处理（{row['status']}）")
        raise ApplicationHandlerStop()

    # success: edit message + remove buttons
    if approve:
        await q.edit_message_text(q.message.text + "\n✅ 已通过（按钮已失效）")
    else:
        await q.edit_message_text(q.message.text + "\n❌ 已拒绝（按钮已失效）")

    raise ApplicationHandlerStop()

def register(app, cfg):
    # make cfg accessible
    app.bot_data["__cfg__"] = cfg

    # use very early group so it runs first
    app.add_handler(CommandHandler("bind", cmd_bind), group=-10000)
    app.add_handler(CommandHandler("requests", cmd_requests), group=-10000)
    app.add_handler(CommandHandler("approve", cmd_approve), group=-10000)
    app.add_handler(CommandHandler("reject", cmd_reject), group=-10000)
    app.add_handler(CallbackQueryHandler(cb_bind, pattern=r"^bind:(approve|reject):\d+$"), group=-10000)
