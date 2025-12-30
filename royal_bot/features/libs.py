# -*- coding: utf-8 -*-
from telegram.ext import CommandHandler

def register(app, ctx):
    ui = ctx["ui"]
    emby = ctx["emby"]
    cfg = ctx["cfg"]

    async def libs(update, context):
        items = await emby.libraries()
        lines = []
        wl = set(cfg.EMBY_LIBRARY_WHITELIST or [])
        for it in items:
            i = str(it.get("Id"))
            n = it.get("Name") or "Unknown"
            tag = "✅ 白名单" if i in wl else ""
            lines.append(f"• <code>{i}</code>  {n} {tag}".strip())
        if not lines:
            lines = ["（没拿到库列表，检查 Emby URL/API Key）"]
        await update.effective_message.reply_html(ui.panel("🎬 Emby 库列表", lines))
    app.add_handler(CommandHandler("libs", libs))
