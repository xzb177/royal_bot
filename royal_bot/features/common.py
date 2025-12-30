# -*- coding: utf-8 -*-
from telegram.ext import CommandHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def register(app, ctx):
    ui = ctx["ui"]

    async def start(update, context):
        u = update.effective_user.first_name
        lines = [
            f"🌸 <b>欢迎来到魔法世界, {u} !</b>",
            "",
            "<b>📖 魔法指南书</b>",
            "",
            "✨ <b>日常魔法</b>",
            "/checkin - 每日祈福 (领心愿值)",
            "/poster - 祈愿抽卡 (抽取回忆)",
            "/wall - 少女收藏册 (看海报)",
            "/me - 我的魔法档案",
            "",
            "🔮 <b>水晶球</b>",
            "/status - 魔镜占卜 (看服务器)",
            "/shop - 魔法小铺 (换道具)",
            "/bounty - 心愿清单 (做任务)",
            "",
            "<i>输入命令，开启你的奇幻之旅吧 ✨</i>"
        ]
        
        # 加一个可爱的按钮
        kb = [[InlineKeyboardButton("🌸 开始祈愿", callback_data="ignore")]] 
        # (按钮暂时只是装饰，为了好看)
        
        await update.effective_message.reply_html(ui.panel("✨ 魔法指南", lines), reply_markup=InlineKeyboardMarkup(kb))

    app.add_handler(CommandHandler(["start", "help", "menu"], start))
