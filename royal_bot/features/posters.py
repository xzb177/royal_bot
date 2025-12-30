# -*- coding: utf-8 -*-
from telegram.ext import CommandHandler
from datetime import datetime
from ..ui import BJ

def _tier_icon(t: str) -> str:
    return {"LEGENDARY":"🏆","EPIC":"💎","RARE":"🎟️","COMMON":"🧾"}.get(t or "", "🖼️")

def register(app, ctx):
    ui = ctx["ui"]
    db = ctx["db"]

    async def posters(update, context):
        uid = update.effective_user.id
        rows = await db.list_posters_text(uid, limit=30)
        if not rows:
            await update.effective_message.reply_html(ui.panel("🖼️ 我的海报收藏", ["还没有收藏，先去 /poster 抽一发 😎"]))
            return

        lines = []
        for i, (title, year, tier, ts) in enumerate(rows, 1):
            dt = datetime.fromtimestamp(int(ts), BJ).strftime("%m-%d %H:%M")
            y = f"({year})" if year else ""
            lines.append(f"{i}. {_tier_icon(tier)} <b>{title}</b> {y}  <i>{dt}</i>")

        await update.effective_message.reply_html(ui.panel("🖼️ 我的海报收藏（最近30）", lines, "收藏=你的私人画廊 😎"))

    app.add_handler(CommandHandler("posters", posters))
