from __future__ import annotations

import html
from datetime import timezone, timedelta
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from .config import CONFIG

CN_TZ = timezone(timedelta(hours=8))

def deeplink(username: str, payload: str) -> str:
    payload = payload.strip()
    return f"https://t.me/{username}?start={payload}"

def _escape(s: str) -> str:
    return html.escape(s, quote=False)

def schedule_delete(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, delay: int):
    if delay <= 0 or not context.application.job_queue:
        return

    async def _do_delete(ctx: ContextTypes.DEFAULT_TYPE):
        try:
            await ctx.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            pass

    context.application.job_queue.run_once(_do_delete, when=delay)

async def reply_html_auto(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    reply_markup=None,
    auto_delete: Optional[bool] = None,
):
    """
    统一回复：HTML parse + 群里自动删 bot 回复（BOT_MSG_TTL）
    """
    msg = update.effective_message
    chat = update.effective_chat

    if not msg:
        return None

    sent = await msg.reply_html(text, reply_markup=reply_markup, disable_web_page_preview=True)

    # 群里默认自动删 bot 回复
    if chat and chat.type in ("group", "supergroup"):
        ttl = int(CONFIG.get("BOT_MSG_TTL", 0) or 0)
        if auto_delete is None:
            auto_delete = ttl > 0
        if auto_delete and ttl > 0:
            schedule_delete(context, chat.id, sent.message_id, ttl)

    return sent
		
		# ====== 少女清新 UI 辅助（追加）======
from .ui import title as ui_title, section as ui_section, tip as ui_tip, soft_divider as ui_soft_divider

def ui_pack(*blocks: str) -> str:
    """把多个块拼成一个清爽面板，中间自动空行。"""
    parts = [b.strip() for b in blocks if b and b.strip()]
    return "\n\n".join(parts).strip()
		