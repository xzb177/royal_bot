# -*- coding: utf-8 -*-
from telegram.ext import CommandHandler
import html

def _badge(i: int) -> str:
    return {1:"🏆", 2:"🥈", 3:"🥉"}.get(i, "•")

async def _name_mention(bot, chat_id: int, uid: int) -> str:
    try:
        m = await bot.get_chat_member(chat_id, uid)
        name = m.user.full_name or m.user.first_name or str(uid)
    except Exception:
        name = str(uid)
    name = html.escape(name)
    return f'<a href="tg://user?id={uid}">{name}</a>'

def register(app, ctx):
    ui = ctx["ui"]
    db = ctx["db"]

    async def winrate(update, context):
        chat_id = update.effective_chat.id
        top = await db.top_winrate(limit=10, min_games=3)
        if not top:
            await update.effective_message.reply_html(ui.panel("🏆 胜率榜", ["还没人打满 3 场～先来一把 /duel 😎"]))
            return

        lines = ["🏆 <b>胜率榜 TOP10</b>（至少 3 场）", ""]
        for i, (uid, w, l, rate, total) in enumerate(top, 1):
            who = await _name_mention(context.bot, chat_id, int(uid))
            lines.append(f"{_badge(i)} {i}. {who}  —  <b>{rate*100:.1f}%</b>  ({w}胜{l}负 / {total}场)")

        await update.effective_message.reply_html(ui.panel("🏆 胜率榜", lines, "胜率就是排面 😎"))

    app.add_handler(CommandHandler("winrate", winrate))
