# -*- coding: utf-8 -*-
from telegram.ext import CommandHandler

PITY_EPIC = 30
PITY_LEG = 80

def _bar(x: int, total: int, width: int = 12) -> str:
    x = max(0, min(total, x))
    filled = int(width * x / total) if total else 0
    return "▰"*filled + "▱"*(width-filled)

def register(app, ctx):
    ui = ctx["ui"]
    db = ctx["db"]

    async def pity(update, context):
        uid = update.effective_user.id
        xp, streak, last_active, last_msg_ts, w, l, pe, pl = await db.get_user(uid)

        epic_left = max(0, PITY_EPIC - pe)
        leg_left  = max(0, PITY_LEG  - pl)

        lines = [
            ui.kv("史诗保底", f"<b>{pe}/{PITY_EPIC}</b>  {_bar(pe, PITY_EPIC)}"),
            ui.kv("传说保底", f"<b>{pl}/{PITY_LEG}</b>  {_bar(pl, PITY_LEG)}"),
            "",
            ui.kv("离史诗还差", f"<b>{epic_left}</b> 抽"),
            ui.kv("离传说还差", f"<b>{leg_left}</b> 抽"),
            "",
            "提示：/poster 每抽一次都会推进保底进度 😎",
        ]
        await update.effective_message.reply_html(ui.panel("🧿 保底进度", lines, "命运不讲理，但保底讲 😎"))

    app.add_handler(CommandHandler("pity", pity))
