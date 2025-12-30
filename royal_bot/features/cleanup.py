from __future__ import annotations

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from ..config import CONFIG
from ..utils import schedule_delete

async def _on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not chat:
        return

    if chat.type not in ("group", "supergroup"):
        return
    if user and user.is_bot:
        return

    delay = int(CONFIG.get("CMD_DELETE_DELAY", 3) or 0)
    if delay <= 0:
        return

    schedule_delete(context, chat.id, msg.message_id, delay)

def register(app: Application):
    app.add_handler(MessageHandler(filters.COMMAND, _on_command), group=999)