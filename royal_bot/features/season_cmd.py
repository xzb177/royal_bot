# -*- coding: utf-8 -*-
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

def _handlers_dict(app):
    h = getattr(app, "handlers", None)
    if not h:
        h = getattr(app, "_handlers", None)
    return h if isinstance(h, dict) else {}

def _find_cmd_handler(app, cmd: str):
    cmd = cmd.lstrip("/").strip()
    for _, hs in _handlers_dict(app).items():
        for h in hs:
            if isinstance(h, CommandHandler):
                try:
                    if cmd in getattr(h, "commands", []):
                        return h
                except Exception:
                    pass
    return None

async def cmd_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    app = context.application

    # 优先转发到你已经稳定可用的榜单命令
    for target in ("bounty", "season"):
        h = _find_cmd_handler(app, target)
        if h and getattr(h, "callback", None):
            await h.callback(update, context)  # type: ignore
            return

    await update.effective_message.reply_text("⚠️ /season 暂时没有绑定到任何榜单处理器（请检查是否加载了 bounty/season 插件）")

def register(app, cfg):
    # group 设小一点，保证比普通 handler 更优先
    app.add_handler(CommandHandler("season", cmd_season), group=-10)

def setup(app, cfg):
    return register(app, cfg)
