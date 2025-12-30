# -*- coding: utf-8 -*-
import os
import re
import sqlite3
import time
from datetime import datetime
from typing import Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes

DB_FILE = os.getenv("DB_FILE", "/root/royal_bot/royal_bot.db")
OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)
GROUP_ID = int(os.getenv("GROUP_ID", "0") or 0)
BIND_REQUIRES_APPROVAL = os.getenv("BIND_REQUIRES_APPROVAL", "1") == "1"

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _db_connect(path: str) -> sqlite3.Connection:
    # 关键：这里必须是 sqlite3.connect，不能递归调用自己
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA busy_timeout=8000;")
    except Exception:
        pass
    return conn

def _with_retry(fn, tries: int = 10, base_sleep: float = 0.12):
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last = e
            msg = str(e).lower()
            if ("locked" in msg) or ("busy" in msg):
                time.sleep(base_sleep * (i + 1))
                continue
            raise
    raise last

def _table_cols(conn: sqlite3.Connection, table: str):
    cur = conn.execute(f"PRAGMA table_info({table})")
    return [r[1] for r in cur.fetchall()]

def _ensure_schema():
    def op():
        conn = _db_connect(DB_FILE)
        cur = conn.cursor()

        # 基础表
        cur.execute("""
        CREATE TABLE IF NOT EXISTS bindings (
            tg_id INTEGER PRIMARY KEY,
            emby_name TEXT NOT NULL
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS bind_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER NOT NULL,
            tg_name TEXT,
            tg_username TEXT,
            emby_name TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT,
            decided_at TEXT
        )
        """)

        # bindings 补列：created_at
        cols = _table_cols(conn, "bindings")
        if "created_at" not in cols:
            cur.execute("ALTER TABLE bindings ADD COLUMN created_at TEXT")
            cur.execute("UPDATE bindings SET created_at=? WHERE created_at IS NULL", (_now(),))

        # bind_requests 补列
        cols2 = _table_cols(conn, "bind_requests")
        if "tg_username" not in cols2:
            cur.execute("ALTER TABLE bind_requests ADD COLUMN tg_username TEXT")
        if "created_at" not in cols2:
            cur.execute("ALTER TABLE bind_requests ADD COLUMN created_at TEXT")
            cur.execute("UPDATE bind_requests SET created_at=? WHERE created_at IS NULL", (_now(),))
        if "decided_at" not in cols2:
            cur.execute("ALTER TABLE bind_requests ADD COLUMN decided_at TEXT")

        conn.commit()
        conn.close()
    return _with_retry(op)

def _is_owner(uid: int) -> bool:
    return bool(OWNER_ID) and uid == OWNER_ID

def _kb_request(rid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ 通过", callback_data=f"bind:approve:{rid}"),
        InlineKeyboardButton("❌ 拒绝", callback_data=f"bind:reject:{rid}"),
    ]])

def _get_binding(tg_id: int) -> Optional[str]:
    _ensure_schema()
    def op():
        conn = _db_connect(DB_FILE)
        cur = conn.execute("SELECT emby_name FROM bindings WHERE tg_id=?", (tg_id,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    return _with_retry(op)

def _set_binding(tg_id: int, emby_name: str):
    _ensure_schema()
    def op():
        conn = _db_connect(DB_FILE)
        cur = conn.cursor()
        # 兼容旧表：可能一开始没有 created_at，我们已 ensure_schema 了
        cur.execute(
            "INSERT INTO bindings(tg_id, emby_name, created_at) VALUES(?,?,?) "
            "ON CONFLICT(tg_id) DO UPDATE SET emby_name=excluded.emby_name",
            (int(tg_id), str(emby_name), _now()),
        )
        conn.commit()
        conn.close()
    return _with_retry(op)

def _new_request(tg_id: int, tg_name: str, tg_username: str, emby_name: str) -> int:
    _ensure_schema()
    def op():
        conn = _db_connect(DB_FILE)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO bind_requests(tg_id, tg_name, tg_username, emby_name, status, created_at) "
            "VALUES(?,?,?,?,?,?)",
            (int(tg_id), str(tg_name or ""), str(tg_username or ""), str(emby_name), "pending", _now()),
        )
        rid = cur.lastrowid
        conn.commit()
        conn.close()
        return int(rid)
    return _with_retry(op)

def _list_pending(limit: int = 30):
    _ensure_schema()
    def op():
        conn = _db_connect(DB_FILE)
        cur = conn.execute(
            "SELECT id, tg_id, tg_name, tg_username, emby_name, created_at "
            "FROM bind_requests WHERE status='pending' ORDER BY id DESC LIMIT ?",
            (int(limit),),
        )
        rows = cur.fetchall()
        conn.close()
        return rows
    return _with_retry(op)

def _decide(rid: int, action: str) -> Tuple[str, Optional[int], Optional[str], Optional[str]]:
    assert action in ("approved", "rejected")
    _ensure_schema()

    def op():
        conn = _db_connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("SELECT tg_id, emby_name, status FROM bind_requests WHERE id=?", (int(rid),))
        row = cur.fetchone()
        if not row:
            conn.close()
            return ("notfound", None, None, None)

        tg_id, emby_name, status = row
        if status != "pending":
            conn.close()
            return ("already", int(tg_id), str(emby_name), str(status))

        cur.execute(
            "UPDATE bind_requests SET status=?, decided_at=? WHERE id=?",
            (action, _now(), int(rid)),
        )
        if action == "approved":
            # 同意就写 bindings
            cur.execute(
                "INSERT INTO bindings(tg_id, emby_name, created_at) VALUES(?,?,?) "
                "ON CONFLICT(tg_id) DO UPDATE SET emby_name=excluded.emby_name",
                (int(tg_id), str(emby_name), _now()),
            )

        conn.commit()
        conn.close()
        return ("ok", int(tg_id), str(emby_name), action)

    return _with_retry(op)

async def cmd_bind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ensure_schema()
    u = update.effective_user
    args = getattr(context, "args", []) or []
    if not args:
        await update.effective_message.reply_text("用法：/bind <Emby用户名>\n例如：/bind yimaodidi")
        return

    emby_name = " ".join(args).strip()
    if not emby_name:
        await update.effective_message.reply_text("🥺 你要绑定的 Emby 用户名不能为空～")
        return

    # 不需要审核 或 管理员本人
    if (not BIND_REQUIRES_APPROVAL) or _is_owner(u.id):
        _set_binding(u.id, emby_name)
        await update.effective_message.reply_text(f"✅ 绑定成功：{emby_name}\n✨ 用 /me 就能看到啦～")
        return

    rid = _new_request(u.id, u.full_name, (u.username or ""), emby_name)
    await update.effective_message.reply_text(
        f"📝 已提交绑定申请（#{rid}）\n"
        f"Emby：{emby_name}\n"
        "⏳ 等管理员审核通过就生效～"
    )

    notify = (
        "👑 Royal Bot｜绑定申请\n"
        f"• 申请号：#{rid}\n"
        f"• TG：{u.full_name} (@{u.username or '-'}) ({u.id})\n"
        f"• Emby：{emby_name}\n\n"
        "（可直接点按钮处理）"
    )

    # 发到群 / 发给管理员：带真正按钮
    try:
        if GROUP_ID:
            await context.bot.send_message(chat_id=GROUP_ID, text=notify, reply_markup=_kb_request(rid))
    except Exception:
        pass
    try:
        if OWNER_ID:
            await context.bot.send_message(chat_id=OWNER_ID, text=notify, reply_markup=_kb_request(rid))
    except Exception:
        pass

async def cmd_unbind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ensure_schema()
    u = update.effective_user
    b = _get_binding(u.id)
    if not b:
        await update.effective_message.reply_text("🍬 你当前还没有绑定记录哦～")
        return

    def op():
        conn = _db_connect(DB_FILE)
        conn.execute("DELETE FROM bindings WHERE tg_id=?", (int(u.id),))
        conn.commit()
        conn.close()
    _with_retry(op)

    await update.effective_message.reply_text("✅ 已解除绑定～")

async def cmd_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ensure_schema()
    u = update.effective_user
    if not _is_owner(u.id):
        await update.effective_message.reply_text("🛑 这个命令只给管理员用哦～")
        return

    rows = _list_pending(30)
    if not rows:
        await update.effective_message.reply_text("💗 当前没有待审核的绑定申请～")
        return

    # 一条申请一条消息，按钮最稳定
    for (rid, tg_id, tg_name, tg_username, emby_name, created_at) in rows:
        tg_show = tg_name or str(tg_id)
        if tg_username:
            tg_show = f"{tg_show} (@{tg_username})"
        msg = (
            "💗 待审核绑定申请：\n"
            f"• 申请号：#{rid}\n"
            f"• TG：{tg_show} ({tg_id})\n"
            f"• Emby：{emby_name}\n"
            f"• 时间：{created_at or '-'}"
        )
        await update.effective_message.reply_text(msg, reply_markup=_kb_request(int(rid)))

async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ensure_schema()
    u = update.effective_user
    if not _is_owner(u.id):
        await update.effective_message.reply_text("🛑 只有管理员可以审核～")
        return
    args = getattr(context, "args", []) or []
    if not args or not str(args[0]).isdigit():
        await update.effective_message.reply_text("用法：/approve 申请号\n例如：/approve 7")
        return
    rid = int(args[0])
    status, tg_id, emby_name, action = _decide(rid, "approved")
    if status == "notfound":
        await update.effective_message.reply_text("找不到这个申请号～")
    elif status == "already":
        await update.effective_message.reply_text(f"这个申请已经处理过了（当前状态：{action}）")
    else:
        await update.effective_message.reply_text(f"✅ 已通过 #{rid}：{tg_id} -> {emby_name}")

async def cmd_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ensure_schema()
    u = update.effective_user
    if not _is_owner(u.id):
        await update.effective_message.reply_text("🛑 只有管理员可以审核～")
        return
    args = getattr(context, "args", []) or []
    if not args or not str(args[0]).isdigit():
        await update.effective_message.reply_text("用法：/reject 申请号\n例如：/reject 7")
        return
    rid = int(args[0])
    status, tg_id, emby_name, action = _decide(rid, "rejected")
    if status == "notfound":
        await update.effective_message.reply_text("找不到这个申请号～")
    elif status == "already":
        await update.effective_message.reply_text(f"这个申请已经处理过了（当前状态：{action}）")
    else:
        await update.effective_message.reply_text(f"❌ 已拒绝 #{rid}：{tg_id} -> {emby_name}")

async def cb_bind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ensure_schema()
    q = update.callback_query
    if not q or not q.data:
        return

    m = re.match(r"^bind:(approve|reject):(\d+)$", q.data)
    if not m:
        return

    u = q.from_user
    if not _is_owner(u.id):
        await q.answer("仅管理员可操作", show_alert=True)
        return

    rid = int(m.group(2))
    action = "approved" if m.group(1) == "approve" else "rejected"
    status, tg_id, emby_name, final = _decide(rid, action)

    if status == "notfound":
        await q.answer("找不到申请号", show_alert=True)
        return
    if status == "already":
        await q.answer("已处理过了", show_alert=False)
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    tip = "✅ 已通过" if action == "approved" else "❌ 已拒绝"
    await q.answer(tip, show_alert=False)

    # 尽量把按钮去掉 & 文本标记已处理
    try:
        new_text = (q.message.text or "") + f"\n\n{tip}（#{rid}）"
        await q.edit_message_text(new_text)
    except Exception:
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

def register(app, cfg=None):
    # 如果 cfg 里有覆盖配置，这里兼容一下（不强依赖）
    global DB_FILE, OWNER_ID, GROUP_ID, BIND_REQUIRES_APPROVAL
    try:
        if cfg is not None:
            DB_FILE = getattr(cfg, "DB_FILE", DB_FILE)
            OWNER_ID = int(getattr(cfg, "OWNER_ID", OWNER_ID) or OWNER_ID)
            GROUP_ID = int(getattr(cfg, "GROUP_ID", GROUP_ID) or GROUP_ID)
            breq = getattr(cfg, "BIND_REQUIRES_APPROVAL", None)
            if breq is not None:
                BIND_REQUIRES_APPROVAL = bool(int(breq)) if str(breq).isdigit() else bool(breq)
    except Exception:
        pass

    _ensure_schema()

    # group 设负数：保证优先于普通文本路由/别的插件
    app.add_handler(CommandHandler("bind", cmd_bind), group=-20)
    app.add_handler(CommandHandler("unbind", cmd_unbind), group=-20)
    app.add_handler(CommandHandler("requests", cmd_requests), group=-20)
    app.add_handler(CommandHandler("approve", cmd_approve), group=-20)
    app.add_handler(CommandHandler("reject", cmd_reject), group=-20)
    app.add_handler(CallbackQueryHandler(cb_bind, pattern=r"^bind:(approve|reject):\d+$"), group=-20)

def setup(app, cfg=None):
    # 兼容有些 loader 叫 setup
    return register(app, cfg)
