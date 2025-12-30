import re
from typing import Optional, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler

APPROVE_RE = re.compile(r"/approve\s+(\d+)")
REJECT_RE  = re.compile(r"/reject\s+(\d+)")
CB_RE      = re.compile(r"^cmd:(approve|reject):(\d+)$")

def _extract_ids(text: str) -> Optional[Tuple[str, str]]:
    if not text:
        return None
    a = APPROVE_RE.search(text)
    r = REJECT_RE.search(text)
    if not a or not r:
        return None
    # 优先用 approve 的 id
    rid = a.group(1)
    return rid, r.group(1)

def _build_kb(req_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ 通过", callback_data=f"cmd:approve:{req_id}"),
            InlineKeyboardButton("❌ 拒绝", callback_data=f"cmd:reject:{req_id}"),
        ]
    ])

def _find_cmd_handler(app: Application, cmd: str) -> Optional[CommandHandler]:
    for group in sorted(app.handlers.keys()):
        for h in app.handlers[group]:
            if isinstance(h, CommandHandler) and cmd in getattr(h, "commands", []):
                return h
    return None

class _ProxyUpdate:
    """让现有 /approve /reject 回调在 CallbackQuery 场景也能用"""
    def __init__(self, update: Update):
        self._u = update
        self.callback_query = update.callback_query
        self.message = None  # 避免 effective_user 误判为 bot
        self.effective_message = update.effective_message
        self.effective_chat = update.effective_chat
        self.effective_user = update.effective_user
        self.effective_sender = getattr(update, "effective_sender", None)

    def __getattr__(self, name):
        return getattr(self._u, name)

async def _on_callback(update: Update, context):
    q = update.callback_query
    if not q or not q.data:
        return
    m = CB_RE.match(q.data)
    if not m:
        return

    action, req_id = m.group(1), m.group(2)
    await q.answer()

    h = _find_cmd_handler(context.application, action)
    if not h:
        await q.message.reply_text(f"⚠️ 找不到命令处理器：/{action}")
        return

    old_args = getattr(context, "args", None)
    try:
        context.args = [req_id]
        await h.callback(_ProxyUpdate(update), context)
    finally:
        context.args = old_args

def _maybe_inject_kb(kwargs, text: str):
    # 用户自己传了 reply_markup 就不动
    if kwargs.get("reply_markup") is not None:
        return
    ids = _extract_ids(text or "")
    if not ids:
        return
    req_id = ids[0]
    kwargs["reply_markup"] = _build_kb(req_id)

def register(app: Application, ctx=None) -> None:
    # 1) 点按钮的回调
    app.add_handler(CallbackQueryHandler(_on_callback, pattern=r"^cmd:(approve|reject):\d+$"), group=0)

    # 2) 自动给消息“注入按钮”（拦截 send_message / edit_message_text）
    bot = app.bot

    if not hasattr(bot, "_ab_orig_send_message"):
        bot._ab_orig_send_message = bot.send_message

        async def _send_message(chat_id, text=None, *args, **kwargs):
            _maybe_inject_kb(kwargs, text or "")
            return await bot._ab_orig_send_message(chat_id, text, *args, **kwargs)

        bot.send_message = _send_message

    if not hasattr(bot, "_ab_orig_edit_message_text"):
        bot._ab_orig_edit_message_text = bot.edit_message_text

        async def _edit_message_text(text=None, *args, **kwargs):
            _maybe_inject_kb(kwargs, text or "")
            return await bot._ab_orig_edit_message_text(text, *args, **kwargs)

        bot.edit_message_text = _edit_message_text
