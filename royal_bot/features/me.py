# -*- coding: utf-8 -*-
import sqlite3
from telegram.ext import CommandHandler, MessageHandler, filters

DB_PATH = "/root/royal_bot/royal.db"

async def me_handler(u, c):
    user = u.effective_user
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        # 严格对齐所有字段
        cur.execute("SELECT emby_account, is_vip, win, lost, points, level, sign_in_days, ssr_count, sr_count, r_count FROM bindings WHERE tg_id = ?", (user.id,))
        row = cur.fetchone()
        conn.close()
        
        acc, is_v, w, l, p, lv, days, ssr, sr, r = row if row else ("未签订", 0, 0, 0, 0, 1, 0, 0, 0, 0)
        status = "💎 皇家圣殿·大祭司 (VIP)" if is_v == 1 else "📜 见习魔法师 (普通)"
        
        text = (
            f"🌸─── <b>{user.first_name} 的魔法手账</b> ───🌸\n\n"
            f"✨ <b>位阶：</b> {status}\n"
            f"🐾 <b>等级：</b> Lv.{lv}  |  💕 <b>灵力：</b> {p}\n"
            f"🗓️ <b>祈愿天数：</b> {days} Day\n\n"
            f"⚔️ <b>战绩：</b> {w}胜 / {l}败\n\n"
            f"🎒 <b>小魔女的手包袋</b>\n"
            f"└ 🌟 SSR: {ssr}  💖 SR: {sr}  🍬 R: {r}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✨ <i>输入 “祈愿” 或 “寻宝” 开启魔法之旅吧！</i>"
        )
        await u.message.reply_html(text)
    except Exception as e:
        await u.message.reply_text(f"⚠️ 档案故障：{str(e)}")

def register(app, ctx):
    app.add_handler(CommandHandler("me", me_handler))
    app.add_handler(MessageHandler(filters.Regex(r'^(名片|/me)$'), me_handler), group=-1)
