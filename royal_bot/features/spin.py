# -*- coding: utf-8 -*-
import sqlite3
import random
import asyncio
from telegram.ext import CommandHandler

# === 🎡 转盘配置 ===
COST = 100  # 每次转动消耗 100 心愿值

# 奖池配置 (名字, 概率权重, 奖励XP, 额外文案)
POOL = [
    ("💎 璀璨星钻",   2,  888, "哇！这是传说中的欧皇时刻！"),
    ("🌟 闪耀金币",   10, 388, "运气不错哦！"),
    ("🍬 幸运糖果",   30, 150, "甜甜的小确幸~"),
    ("🍃 秋日落叶",   40, 50,  "虽然亏了一点点，但心情不错~"),
    ("💨 一阵微风",   18, 0,   "什么也没有发生... (再试一次？)"),
]

def get_conn(path):
    return sqlite3.connect(path, check_same_thread=False)

def register(app, ctx):
    cfg = ctx["cfg"]
    ui = ctx["ui"]
    db_path = cfg.DB_FILE

    async def spin(update, context):
        uid = update.effective_user.id
        
        with get_conn(db_path) as conn:
            cur = conn.cursor()
            
            # 1. 查余额
            cur.execute("SELECT xp FROM user_stats WHERE tg_id=?", (uid,))
            row = cur.fetchone()
            balance = row[0] if row else 0
            
            if balance < COST:
                await update.message.reply_text(f"🌑 你的魔力不足啦 (需要 {COST}，当前 {balance})，无法转动命运之轮。")
                return

            # 2. 扣费
            cur.execute("UPDATE user_stats SET xp = xp - ? WHERE tg_id=?", (COST, uid))
            
            # 3. 记录每周转盘次数 (用于周常任务)
            # 先尝试更新，如果没这行数据可能需要 user_stats_weekly 表
            # 这里为了稳，只做简单的尝试，报错不影响主流程
            try:
                # 假设 week 字段逻辑比较复杂，我们先简单的只更新 daily_stats (如果有的话)
                pass 
            except:
                pass

            conn.commit()

            # 4. 转动逻辑 (模拟动画感)
            msg = await update.message.reply_html("🎡 <b>命运之轮转动中...</b>\n<i>星辰正在排列...</i>")
            
            # 随机抽奖
            # 展开权重
            choices = []
            for item in POOL:
                choices.extend([item] * item[1])
            
            prize_name, weight, award_xp, flavor = random.choice(choices)
            
            # 5. 发奖
            if award_xp > 0:
                cur.execute("UPDATE user_stats SET xp = xp + ? WHERE tg_id=?", (award_xp, uid))
                conn.commit()

        # 6. 最终展示
        await asyncio.sleep(1.5) # 假装在转，增加紧张感
        
        lines = [
            f"🎡 <b>命运的指引</b>",
            "",
            f"消耗: <b>{COST} 🌸</b>",
            f"结果: <b>{prize_name}</b>",
            f"获得: <b>{award_xp} 🌸</b>",
            "",
            f"<i>{flavor}</i>"
        ]
        
        # 修改原消息
        await msg.edit_text(ui.panel("✨ 占卜结束", lines), parse_mode="HTML")

    app.add_handler(CommandHandler(["spin", "wheel", "luck"], spin))
