# -*- coding: utf-8 -*-
import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters

ADMIN_ID = 5779291957
DB_PATH = "/root/royal_bot/royal.db"

async def bind_magic(u, c):
    if not u.message or not u.message.text: return
    text = u.message.text.strip()
    
    # 少女心判定：支持 "绑定 账号"、"绑定账号"、"/bind 账号"
    import re
    # 匹配“绑定”或“/bind”开头，后面跟或不跟空格的所有字符
    match = re.search(r'^(?:绑定|/bind)\s*(.*)', text, re.I)
    acc = match.group(1).strip() if match else ""
    
    user = u.effective_user
    if not acc:
        return await u.message.reply_html("🎀 <b>“唔... 想要和云海签订契约吗？”</b>\n\n请发送 <code>绑定 账号</code> 告诉我你的名字吧，我会带你去圣殿哒！✨")
    
    # 账号脱敏处理
    acc_safe = acc[:25]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ 批准契约", callback_data=f"adm_ok:{user.id}:{acc_safe}")],
        [InlineKeyboardButton("💎 授予·皇家身份", callback_data=f"adm_wt:{user.id}:{acc_safe}")]
    ])
    
    await c.bot.send_message(chat_id=ADMIN_ID, text=f"📜 <b>圣殿传回一份新契约！</b>\n\n👤 申请灵：{user.first_name}\n📺 欲绑账号：<code>{acc_safe}</code>\n🆔 ID：<code>{user.id}</code>\n\n大魔导师大人，请赐予指令：", parse_mode='HTML', reply_markup=kb)
    await u.message.reply_html("🕊️ <b>契约已送往星光云端~</b>\n请在这里稍等片刻，神谕很快就会降临哦！🌸")

async def callback_handler(u, c):
    q = u.callback_query
    data = q.data.split(":")
    tid, acc, action = int(data[1]), data[2], data[0]
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO bindings (tg_id, emby_account, is_vip) VALUES (?, '未签订', 0)", (tid,))
    # 强制锁死 is_vip 字段，确保名片显示正常
    is_v = 1 if action == "adm_wt" else 0
    cur.execute("UPDATE bindings SET emby_account = ?, is_vip = ? WHERE tg_id = ?", (acc, is_v, tid))
    conn.commit()
    conn.close()
    
    await q.edit_message_text(f"✨ <b>神谕已达成：</b> {acc} 的档案已更新")
    try:
        msg = "🌟 <b>哇！恭喜你成为圣殿成员！</b> 专属星光已经为你点亮啦！" if is_v else "🌸 <b>签订成功！</b> 契约已经生效，快去名片看看吧~"
        await c.bot.send_message(chat_id=tid, text=msg, parse_mode='HTML')
    except: pass

def register(app, ctx):
    # 使用最高优先级 group=-1，确保不被其他闲聊插件拦截
    app.add_handler(MessageHandler(filters.Regex(r'^(绑定|/bind)'), bind_magic), group=-1)
    app.add_handler(CallbackQueryHandler(callback_handler, pattern="^adm_"))
