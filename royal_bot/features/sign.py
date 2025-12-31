# -*- coding: utf-8 -*-
import sqlite3, datetime, random
from telegram.ext import MessageHandler, filters

DB_PATH = "/root/royal_bot/royal.db"

async def sign_handler(u, c):
    user = u.effective_user
    today = datetime.date.today().isoformat()
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO bindings (tg_id) VALUES (?)", (user.id,))
    cur.execute("SELECT last_sign_date, sign_in_days FROM bindings WHERE tg_id = ?", (user.id,))
    last_date, days = cur.fetchone()
    
    if last_date == today:
        conn.close()
        return await u.message.reply_html(f"🎀 <b>“唔...”</b>\n\n{user.first_name}，今天的星光能量已经采满啦，明天再来祈愿吧~ 🌸")
    
    add_pts = random.randint(30, 80)
    new_days = days + 1
    cur.execute("UPDATE bindings SET last_sign_date=?, sign_in_days=?, points=points+? WHERE tg_id=?", (today, new_days, add_pts, user.id))
    conn.commit()
    conn.close()
    
    await u.message.reply_html(
        f"✨ <b>祈愿达成 · 灵力注入</b> ✨\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🌸 <b>获得灵力：</b> +{add_pts}\n"
        f"🗓️ <b>连续祈愿：</b> {new_days} 天\n\n"
        f"<i>“心诚则灵，今天的你也是闪闪发光的少女呢~”</i>"
    )

def register(app, ctx):
    app.add_handler(MessageHandler(filters.Regex(r'^(祈愿|签到)$'), sign_handler), group=-1)
