# -*- coding: utf-8 -*-
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import MessageHandler, filters

def register(app, ctx):
    async def welcome(update, context):
        for member in update.message.new_chat_members:
            # 跳过机器人自己
            if member.id == context.bot.id: continue
            
            # 欢迎文案
            name = member.first_name
            text = (
                f"✨ <b>欢迎来到魔法世界，{name}！</b>\n\n"
                f"我是这里的魔法管家。想要在云海畅游，你需要先了解以下咒语：\n\n"
                f"📝 <b>绑定账号：</b>发送 <code>绑定 你的Emby账号</code>\n"
                f"📅 <b>获取魔力：</b>发送 <code>每日祈福</code>\n"
                f"🎬 <b>抽取海报：</b>发送 <code>命运祈愿</code>\n\n"
                f"<i>祝你在云海旅途愉快！🧙‍♀️</i>"
            )
            
            # 快捷按钮
            kb = [
                [InlineKeyboardButton("📖 打开魔法书 (菜单)", callback_data="menu_main")],
                [InlineKeyboardButton("💎 立即签订契约", switch_inline_query_current_chat="绑定 ")]
            ]
            
            await update.message.reply_html(text, reply_markup=InlineKeyboardMarkup(kb))

    # 监听“新成员加入”事件
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
