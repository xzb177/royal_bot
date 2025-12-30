# -*- coding: utf-8 -*-
import sqlite3
from telegram.ext import CommandHandler

def get_conn(path):
    return sqlite3.connect(path, check_same_thread=False)

def register(app, ctx):
    cfg = ctx["cfg"]
    db_path = cfg.DB_FILE

    async def transfer(update, context):
        msg = update.effective_message
        sender = update.effective_user
        
        # 1. 必须回复一个人
        if not msg.reply_to_message:
            await msg.reply_text("🎁 请回复你想赠送的那位伙伴的消息哦~")
            return
            
        receiver = msg.reply_to_message.from_user
        if receiver.id == sender.id:
            await msg.reply_text("🎁 左手倒右手是不行的哦~")
            return
        if receiver.is_bot:
            await msg.reply_text("🤖 机器人不需要心愿值，留给你自己吧！")
            return

        # 2. 解析金额
        try:
            amount = int(context.args[0])
        except:
            await msg.reply_text("💫 格式不对啦！\n正确咒语：/gift [数量]\n例如：/gift 100")
            return
            
        if amount <= 0:
            await msg.reply_text("🌸 礼物不能是空的哦~")
            return

        # 3. 执行转账
        with get_conn(db_path) as conn:
            cur = conn.cursor()
            
            # 查发送者余额
            cur.execute("SELECT xp FROM user_stats WHERE tg_id=?", (sender.id,))
            row = cur.fetchone()
            if not row or row[0] < amount:
                await msg.reply_text(f"💸 你的魔力不足啦 (拥有: {row[0] if row else 0})，无法赠送。")
                return
            
            # 查接收者 (补档)
            cur.execute("SELECT xp FROM user_stats WHERE tg_id=?", (receiver.id,))
            if not cur.fetchone():
                cur.execute("INSERT INTO user_stats (tg_id, xp) VALUES (?, 0)", (receiver.id,))

            # 扣款 & 入账 (原子操作)
            cur.execute("UPDATE user_stats SET xp = xp - ? WHERE tg_id=?", (amount, sender.id))
            cur.execute("UPDATE user_stats SET xp = xp + ? WHERE tg_id=?", (amount, receiver.id))
            conn.commit()

            await msg.reply_html(
                f"🎁 <b>心意传递成功！</b>\n\n"
                f"💖 <b>{sender.first_name}</b> 赠送给了 <b>{receiver.first_name}</b>\n"
                f"🌸 <b>{amount} 点心愿值</b>\n\n"
                f"<i>这就是魔法世界的友谊吗？爱了爱了~ ✨</i>"
            )

    # 注册 /pay 和 /gift 两个命令
    app.add_handler(CommandHandler(["gift", "pay", "give"], transfer))
