# -*- coding: utf-8 -*-
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler

async def shop(update, context):
    user = update.effective_user
    is_v = True if user.id in [6803708307] else False
    
    # 商店 UI 构造 (情绪拉满版)
    title = "✨💎 <b>皇家魔法小铺</b> 💎✨" if is_v else "🔮 <b>魔法小铺</b> 🔮"
    vip_note = "\n🌟 <b>VIP 特权：</b> <code>全场魔法道具 9 折</code>" if is_v else ""
    
    text = (
        f"{title}\n"
        f"━━━━━━━━━━━━━━\n"
        f"🌸 欢迎光临，<b>{user.first_name}</b>！\n"
        f"在这里，您可以用心愿值兑换神秘道具。{vip_note}\n\n"
        f"📦 <b>今日魔法货架：</b>\n"
        f"🍬 <code>甜心教主</code> - 60 🌸\n"
        f"👑 <code>月光公主</code> - 120 🌸\n"
        f"🌹 <code>蔷薇女王</code> - 220 🌸\n"
        f"⚡ <code>雷霆之主</code> - 500 🌸\n"
        f"━━━━━━━━━━━━━━\n"
        f"请点击下方按钮，开始您的兑换仪式吧 ✨"
    )
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍬 购买: 甜心教主", callback_data="buy:candy")],
        [InlineKeyboardButton("👑 购买: 月光公主", callback_data="buy:princess")],
        [InlineKeyboardButton("🌹 购买: 蔷薇女王", callback_data="buy:rose")],
        [InlineKeyboardButton("⚡ 购买: 雷霆之主", callback_data="buy:thunder")]
    ])
    
    await update.message.reply_html(text, reply_markup=kb)

def register(app, ctx):
    app.add_handler(CommandHandler("shop", shop))
