# -*- coding: utf-8 -*-
import sqlite3, random, asyncio
from telegram.ext import MessageHandler, filters

DB_PATH = "/root/royal_bot/royal.db"

async def gacha_handler(u, c):
    user = u.effective_user
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        cur = conn.cursor()
        cur.execute("SELECT points FROM bindings WHERE tg_id = ?", (user.id,))
        res = cur.fetchone()
        pts = res[0] if res else 0
        
        if pts < 100:
            conn.close()
            return await u.message.reply_html(f"🍭 <b>“灵力不足...”</b>\n\n寻宝需要 100 灵力，你只有 {pts} 点哦~")
        
        status_msg = await u.message.reply_html("🔮 <b>星光占卜中...</b>\n🪄 正在从异次元召唤宝物...")
        
        luck = random.random()
        if luck < 0.05: item, col = "🌟 SSR【幻彩星石】", "ssr_count"
        elif luck < 0.25: item, col = "💖 SR【琉璃羽毛】", "sr_count"
        else: item, col = "🍬 R【魔力糖果】", "r_count"
        
        cur.execute(f"UPDATE bindings SET points = points - 100, {col} = {col} + 1 WHERE tg_id = ?", (user.id,))
        conn.commit()
        conn.close()
        
        await asyncio.sleep(0.8)
        await status_msg.edit_text(f"🎊 <b>寻宝成功！</b>\n🎁 获得：{item}\n📊 已存入手包袋！", parse_mode='HTML')
    except Exception as e:
        await u.message.reply_text(f"⚠️ 寻宝反噬：{str(e)}")

def register(app, ctx):
    # 简化正则，只匹配“寻宝”和“抽卡”
    app.add_handler(MessageHandler(filters.Regex(r'^(寻宝|抽卡)$'), gacha_handler), group=-1)
