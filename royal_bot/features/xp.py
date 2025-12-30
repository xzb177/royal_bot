# -*- coding: utf-8 -*-
import time
from datetime import datetime, timezone, timedelta
from telegram.ext import CommandHandler, MessageHandler, filters

BJ = timezone(timedelta(hours=8))
DAY_FMT = '%Y-%m-%d'
WEEK_FMT = 'iso'
COOLDOWN = 15  # 秒：防刷屏加速

def register(app, ctx):
    ui = ctx["ui"]
    db = ctx["db"]

    async def xp_cmd(update, context):
        uid = update.effective_user.id
        xp, streak, last_active, last_msg_ts, w, l, pe, pl = await db.get_user(uid)
        lines = [
            ui.kv("XP", f"<b>{xp}</b>"),
            ui.kv("连胜", f"<b>{streak}</b> 天"),
            ui.kv("决斗", f"<b>{w}</b>胜 / <b>{l}</b>负"),
        ]
        await update.effective_message.reply_html(ui.panel("📈 XP 成长面板", lines, "你不是在水群，你是在升级成老板 😎"))

    async def chat_gain(update, context):
        if not update.effective_message or not update.effective_user:
            return
        if update.effective_user.is_bot:
            return
        if update.effective_message.text and update.effective_message.text.startswith("/"):
            return

        uid = update.effective_user.id
        xp, streak, last_active, last_msg_ts, w, l, pe, pl = await db.get_user(uid)

        now_ts = int(time.time())
        if now_ts - int(last_msg_ts or 0) < COOLDOWN:
            return

        # 每条消息 +1 XP（你要更猛我也能做成随机 1~3）
        await db.add_xp(uid, 1)
        await db.set_msg_ts(uid, now_ts)
        day = datetime.now(BJ).strftime(DAY_FMT)
        await db.inc_daily_stat(uid, day, 'msgs', 1)
        iso = datetime.now(BJ).isocalendar()
        week = f"{iso.year}-W{iso.week:02d}"
        await db.inc_weekly_stat(uid, week, 'msgs', 1)

        today = datetime.now(BJ).strftime("%Y-%m-%d")
        if last_active != today:
            # 新的一天：连胜+1
            await db.set_streak(uid, streak + 1, today)

    app.add_handler(CommandHandler("xp", xp_cmd))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), chat_gain))
