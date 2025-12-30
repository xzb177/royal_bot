from __future__ import annotations
import re
from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

async def _call_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, cmd: str, args: list[str]) -> bool:
    app = context.application
    for group in sorted(app.handlers.keys()):
        for h in app.handlers[group]:
            if isinstance(h, CommandHandler) and cmd in getattr(h, "commands", []):
                try:
                    context.args = list(args)
                except Exception:
                    pass
                await h.callback(update, context)  # type: ignore[attr-defined]
                return True
    return False

async def _bind_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q:
        return
    await q.answer()
    m = re.match(r"^bind:(approve|reject):(\d+)$", q.data or "")
    if not m:
        return
    action, rid = m.group(1), m.group(2)
    ok = await _call_cmd(update, context, action, [rid])
    # 通过后尽量把按钮去掉，避免重复点
    if ok:
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

def register(app, cfg):
    app.add_handler(CallbackQueryHandler(_bind_cb, pattern=r"^bind:(approve|reject):\d+$"), group=50)
