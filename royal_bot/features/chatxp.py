# /root/royal_bot/royal_bot/features/chatxp.py
from __future__ import annotations

from datetime import date

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from ..db import DB

# ====== 配置：老板上头版 ======
MSG_PER_XP = 10            # 10条消息 = 1 XP
DAILY_XP_CAP = 200         # 每日最多 200 XP
MILESTONES = (50, 100, 200)


def ensure_schema() -> None:
    DB.exec("""
    CREATE TABLE IF NOT EXISTS chatxp_daily (
        tg_id INTEGER NOT NULL,
        day TEXT NOT NULL,
        msg_count INTEGER NOT NULL DEFAULT 0,
        xp_gained INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (tg_id, day)
    )
    """)
    # 确保 user_stats 存在你那边一般已经有，但补一层保险不亏
    DB.exec("""
    CREATE TABLE IF NOT EXISTS user_stats (
        tg_id INTEGER PRIMARY KEY,
        duels_won INTEGER DEFAULT 0,
        duels_lost INTEGER DEFAULT 0,
        xp INTEGER DEFAULT 0,
        streak INTEGER DEFAULT 0,
        flex_count INTEGER DEFAULT 0
    )
    """)


def _today() -> str:
    return date.today().isoformat()


def _ensure_daily_row(tg_id: int, day: str):
    DB.exec("INSERT OR IGNORE INTO chatxp_daily (tg_id, day) VALUES (?,?)", (tg_id, day))


def _get_daily(tg_id: int, day: str) -> tuple[int, int]:
    _ensure_daily_row(tg_id, day)
    row = DB.fetch("SELECT msg_count, xp_gained FROM chatxp_daily WHERE tg_id=? AND day=?", (tg_id, day))
    if not row:
        return 0, 0
    return int(row[0]), int(row[1])


def _set_daily(tg_id: int, day: str, msg_count: int, xp_gained: int) -> None:
    DB.exec(
        "UPDATE chatxp_daily SET msg_count=?, xp_gained=? WHERE tg_id=? AND day=?",
        (msg_count, xp_gained, tg_id, day),
    )


def _add_xp(tg_id: int, delta: int) -> None:
    DB.exec("INSERT OR IGNORE INTO user_stats (tg_id) VALUES (?)", (tg_id,))
    DB.exec("UPDATE user_stats SET xp = COALESCE(xp,0) + ? WHERE tg_id=?", (delta, tg_id))


async def _on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.effective_chat or not update.effective_message:
        return

    # 只算群聊
    if update.effective_chat.type not in ("group", "supergroup"):
        return

    tg_id = update.effective_user.id
    day = _today()

    msg_count, xp_gained = _get_daily(tg_id, day)

    # 今日封顶
    if xp_gained >= DAILY_XP_CAP:
        return

    msg_count += 1

    gained_now = 0
    if msg_count % MSG_PER_XP == 0:
        gained_now = 1
        xp_gained += 1
        _add_xp(tg_id, 1)

    if xp_gained > DAILY_XP_CAP:
        xp_gained = DAILY_XP_CAP

    _set_daily(tg_id, day, msg_count, xp_gained)

    # 里程碑播报（只在刚好触发 XP 时播报）
    if gained_now and xp_gained in MILESTONES:
        await update.effective_message.reply_text(
            f"🏁 {update.effective_user.full_name} 今日聊天声望突破 {xp_gained} XP！\n"
            f"👑 这不是水群，这是在群里立王朝。",
            disable_web_page_preview=True,
        )


def register(app, ctx):
    # 文本消息算 XP（忽略命令）
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_message))