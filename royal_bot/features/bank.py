# -*- coding: utf-8 -*-
import sqlite3
import random
import time
from telegram.ext import CommandHandler

def get_conn(path):
    return sqlite3.connect(path, check_same_thread=False)

def register(app, ctx):
    cfg = ctx["cfg"]
    db_path = cfg.DB_FILE

    async def loan(update, context):
        user = update.effective_user
        uid = user.id
        
        # 1. 只有穷人才能借钱 (心愿值低于 50)
        with get_conn(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT xp FROM user_stats WHERE tg_id=?", (uid,))
            row = cur.fetchone()
            balance = row[0] if row else 0
            
            if balance >= 50:
                await update.message.reply_text("🏦 <b>魔法银行拒绝了您的请求</b>\n\n经理：<i>“您身上还有钱呢，别想骗保底！去 /daily 祈福吧！”</i>", parse_mode="HTML")
                return

            # 2. 发放救济金 (100 ~ 300 随机)
            loan_amount = random.randint(100, 300)
            cur.execute("UPDATE user_stats SET xp = xp + ? WHERE tg_id=?", (loan_amount, uid))
            conn.commit()

        # 3. 发送回执
        await update.message.reply_html(
            f"🏦 <b>魔法银行放款通知</b>\n\n"
            f"💸 批准对象: <b>{user.first_name}</b>\n"
            f"💰 发放金额: <b>{loan_amount} 🌸</b>\n\n"
            f"📝 <i>行长寄语：拿着这些钱，去 /duel 赢回来吧！(如果不幸输光了...明天再来)</i>"
        )

    app.add_handler(CommandHandler(["loan", "borrow", "money"], loan))
