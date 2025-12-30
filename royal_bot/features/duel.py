# -*- coding: utf-8 -*-
import sqlite3
import random
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler

def get_conn(path):
    return sqlite3.connect(path, check_same_thread=False)

# 内存暂存: {target_id: (challenger_id, amount, challenger_name)}
PENDING = {}

def register(app, ctx):
    cfg = ctx["cfg"]
    db_path = cfg.DB_FILE
    
    # === 1. 发起挑战 ===
    async def duel(update, context):
        msg = update.effective_message
        user = update.effective_user
        
        if not msg.reply_to_message:
            await msg.reply_text("⚔️ 请回复你想切磋的人哦~")
            return
            
        target = msg.reply_to_message.from_user
        if target.id == user.id:
            await msg.reply_text("🪞 不能跟自己打架哦~")
            return
        if target.is_bot:
            await msg.reply_text("🤖 机器人无法应战。")
            return

        try:
            amount = int(context.args[0]) if context.args else 50
        except:
            await msg.reply_text("💫 格式错误！例如：/duel 50")
            return
            
        if amount < 10:
            await msg.reply_text("🌸 至少投入 10 点心愿值。")
            return

        # 查钱
        with get_conn(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT xp FROM user_stats WHERE tg_id=?", (user.id,))
            row = cur.fetchone()
            if not row or row[0] < amount:
                await msg.reply_text(f"💸 魔力不足 ({row[0] if row else 0})，去签到领点吧！")
                return

        # 记录邀请 (把名字也存进去)
        PENDING[target.id] = (user.id, amount, user.first_name)
        
        kb = [[
            InlineKeyboardButton("⚔️ 接受练习", callback_data=f"duel:yes:{user.id}:{amount}"),
            InlineKeyboardButton("🏳️ 还是算了", callback_data=f"duel:no:{user.id}")
        ]]
        
        await msg.reply_html(
            f"⚔️ <b>魔法切磋邀请</b>\n\n"
            f"⚡️ <b>{user.first_name}</b> 向 <b>{target.first_name}</b> 发起了挑战！\n"
            f"✨ 投入魔力: <b>{amount} 🌸</b>\n\n"
            f"<i>{target.first_name}，请点击下方按钮决定：</i>",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    # === 2. 按钮回调 ===
    async def duel_callback(update, context):
        q = update.callback_query
        data = q.data.split(":") 
        action = data[1]
        clicker = q.from_user
        
        if action == "no":
            # === 拒绝 ===
            if clicker.id in PENDING:
                del PENDING[clicker.id]
                await q.answer("已拒绝")
                await q.edit_message_text(f"🏳️ <b>{clicker.first_name}</b> 婉拒了这次切磋。", parse_mode="HTML")
            else:
                await q.answer("这主要不是问你的哦~", show_alert=True)
            return

        elif action == "rematch":
            # === 再来一局 ===
            # data: duel:rematch:target_id:amount
            target_id = int(data[2])
            amount = int(data[3])
            
            # 查钱
            with get_conn(db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT xp FROM user_stats WHERE tg_id=?", (clicker.id,))
                row = cur.fetchone()
                if not row or row[0] < amount:
                    await q.answer("魔力不足，无法复仇！", show_alert=True)
                    return

            # 直接发起新邀请
            PENDING[target_id] = (clicker.id, amount, clicker.first_name)
            
            kb = [[
                InlineKeyboardButton("⚔️ 接受练习", callback_data=f"duel:yes:{clicker.id}:{amount}"),
                InlineKeyboardButton("🏳️ 还是算了", callback_data=f"duel:no:{clicker.id}")
            ]]
            
            # 发送到群里
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"🔄 <b>{clicker.first_name}</b> 不服气，要求再来一局！\n✨ 投入: <b>{amount} 🌸</b>",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="HTML"
            )
            await q.answer("复仇书已下达！")
            return

        elif action == "yes":
            # === 接受 (计算胜负) ===
            challenger_id = int(data[2])
            amount = int(data[3])
            
            if clicker.id not in PENDING or PENDING[clicker.id][0] != challenger_id:
                await q.answer("这张挑战书好像过期了，或者不是给你的", show_alert=True)
                return
            
            # === 关键修复：先获取名字，再删记录 ===
            challenger_name = PENDING[clicker.id][2]
            target_name = clicker.first_name
            
            del PENDING[clicker.id]
            
            # 结算数据库
            with get_conn(db_path) as conn:
                cur = conn.cursor()
                # 查双方余额
                cur.execute("SELECT xp FROM user_stats WHERE tg_id=?", (challenger_id,))
                c_row = cur.fetchone()
                cur.execute("SELECT xp FROM user_stats WHERE tg_id=?", (clicker.id,))
                t_row = cur.fetchone()
                
                c_xp = c_row[0] if c_row else 0
                t_xp = t_row[0] if t_row else 0
                
                if c_xp < amount:
                    await q.answer("挑战者没钱了！")
                    await q.edit_message_text(f"🕊️ <b>{challenger_name}</b> 的魔力耗尽了，比赛取消。", parse_mode="HTML")
                    return
                if t_xp < amount:
                    await q.answer("你没钱了！")
                    return

                # 🎲 随机胜负
                winner_id = challenger_id if random.random() > 0.5 else clicker.id
                loser_id = clicker.id if winner_id == challenger_id else challenger_id
                
                # 确定赢家名字和输家名字
                if winner_id == challenger_id:
                    winner_name = challenger_name
                    loser_name = target_name
                else:
                    winner_name = target_name
                    loser_name = challenger_name

                # 资金转移
                cur.execute("UPDATE user_stats SET xp = xp + ? WHERE tg_id=?", (amount, winner_id))
                cur.execute("UPDATE user_stats SET xp = xp - ? WHERE tg_id=?", (amount, loser_id))
                
                # 记录胜场
                try:
                    cur.execute("UPDATE user_stats SET duels_won = duels_won + 1 WHERE tg_id=?", (winner_id,))
                except: pass
                conn.commit()

            # ✨ 结果展示
            spells = ["✨ 统统石化！", "🔥 霹雳爆炸！", "💫 昏昏倒地！", "🌊 清水如泉！", "❄️ 冰冻三尺！"]
            spell = random.choice(spells)
            
            # 生成复仇按钮 (发给刚才输的人去点，或者赢的人继续挑战)
            # data里的ID放当前的赢家，意味着点这个按钮是向赢家发起挑战
            rematch_kb = [[
                InlineKeyboardButton("🔄 不服！再来一局", callback_data=f"duel:rematch:{winner_id}:{amount}")
            ]]

            await q.edit_message_text(
                f"⚔️ <b>切磋结束！</b>\n\n"
                f"⚡️ 咒语光芒闪过：<b>{spell}</b>\n\n"
                f"🏆 <b>胜利者: {winner_name}</b> (+{amount} 🌸)\n"
                f"🤕 <b>惜败: {loser_name}</b> (-{amount} 🌸)\n\n"
                f"<i>(胜负乃兵家常事~)</i>",
                reply_markup=InlineKeyboardMarkup(rematch_kb),
                parse_mode="HTML"
            )

    app.add_handler(CommandHandler("duel", duel))
    app.add_handler(CallbackQueryHandler(duel_callback, pattern=r"^duel:"))
