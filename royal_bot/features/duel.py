# -*- coding: utf-8 -*-
import random, asyncio, sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters

DB_PATH = "/root/royal_bot/royal.db"

async def duel_handler(u, c):
    user = u.effective_user
    p = random.randint(30, 80)
    text = (f"⚔️✨ <b>魔法切磋邀请函</b> ✨⚔️\n━━━━━━━━━━━━━━━━━━\n"
            f"🎀 <b>发起灵：</b> {user.first_name}\n"
            f"🌸 <b>赌注灵力：</b> {p} 点\n\n"
            f"✨ <i>“要来一场华丽的魔法对碰吗？输了的人不许哭鼻子哦~”</i>")
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⚔️ 接受切磋", callback_data=f"duel_acc:{user.id}:{p}"),
        InlineKeyboardButton("🏳️ 躲起来", callback_data=f"duel_can:{user.id}")
    ]])
    await u.message.reply_html(text, reply_markup=kb)

async def callback(u, c):
    q = u.callback_query
    if q.data.startswith("duel_acc"):
        p, cid, me = int(q.data.split(":")[2]), int(q.data.split(":")[1]), u.effective_user
        if me.id == cid: return await q.answer("❌ 哎呀！不能和镜子里的自己打架呢~", show_alert=True)
        await q.edit_message_text("🌪️ <b>星光汇聚中...🪄 奇迹判定开始！</b>", parse_mode='HTML')
        await asyncio.sleep(1.2)
        win_id, lose_id = random.sample([cid, me.id], 2)
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        for uid in [win_id, lose_id]: cur.execute("INSERT OR IGNORE INTO bindings (tg_id, emby_account, is_vip) VALUES (?, '未签订', 0)", (uid,))
        cur.execute("UPDATE bindings SET win=win+1, points=points+? WHERE tg_id=?", (p, win_id))
        cur.execute("UPDATE bindings SET lost=lost+1, points=points-? WHERE tg_id=?", (p, lose_id))
        conn.commit()
        conn.close()
        w_n = (await c.bot.get_chat(win_id)).first_name
        await q.edit_message_text(f"🏆 <b>切磋落幕 · 华丽绽放</b>\n\n✨ <b>优胜者：</b> {w_n}\n🌸 <b>获得灵力：</b> +{p}\n\n📊 战果已同步，快去 <code>/me</code> 看看吧~", parse_mode='HTML')

def register(app, ctx):
    # 使用 group=-1 提升拦截优先级
    app.add_handler(MessageHandler(filters.Regex(r'^(对决|魔法对决|/duel)'), duel_handler), group=-1)
    app.add_handler(CallbackQueryHandler(callback, pattern="^duel_"))
