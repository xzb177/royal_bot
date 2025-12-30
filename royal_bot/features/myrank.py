# -*- coding: utf-8 -*-
from telegram.ext import CommandHandler

def register(app, ctx):
    ui = ctx["ui"]
    db = ctx["db"]

    async def myrank(update, context):
        uid = update.effective_user.id
        xp, streak, last_active, last_msg_ts, w, l, pe, pl = await db.get_user(uid)
        rank = await db.rank_xp(uid)
        total = w + l
        rate = (w / total) * 100 if total else 0.0

        lines = [
            ui.kv("XP", f"<b>{xp}</b>"),
            ui.kv("排名", f"<b>#{rank}</b>"),
            ui.kv("连胜", f"<b>{streak}</b> 天"),
            ui.kv("决斗战绩", f"<b>{w}</b>胜 / <b>{l}</b>负"),
            ui.kv("胜率", f"<b>{rate:.1f}%</b>（{total}场）"),
        ]
        await update.effective_message.reply_html(ui.panel("🎖️ 我的排面面板", lines, "老板，数据就是排面 😎"))

    app.add_handler(CommandHandler("myrank", myrank))
