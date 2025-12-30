# -*- coding: utf-8 -*-
import sqlite3
import random
import time
from telegram.ext import CommandHandler

def get_conn(path): return sqlite3.connect(path, check_same_thread=False)

# 🔮 运势文案配置
FORTUNES = [
    ("🌟 大吉", 300, 500, "星辰眷顾着你！今天抽卡必出 SSR！"),
    ("🌸 中吉", 200, 300, "魔力充盈，适合去决斗场一展身手。"),
    ("✨ 小吉", 100, 200, "平平淡淡才是真，去看看电影吧。"),
    ("🌪 末吉", 50, 100, "今天不宜剧烈运动，适合躺在家里。"),
    ("⚡️ 凶", 10, 50, "不要在这个时候进行危险的魔法实验！")
]

def register(app, ctx):
    cfg = ctx["cfg"]
    db_path = cfg.DB_FILE

    async def daily(update, context):
        user = update.effective_user
        uid = user.id
        now = int(time.time())
        
        # 1. 检查冷却 (一天 86400 秒)
        with get_conn(db_path) as conn:
            cur = conn.cursor()
            # 确保表结构完整
            try: cur.execute("ALTER TABLE user_stats ADD COLUMN last_daily INTEGER DEFAULT 0")
            except: pass
            
            cur.execute("SELECT last_daily, xp, streak FROM user_stats WHERE tg_id=?", (uid,))
            row = cur.fetchone()
            
            if not row:
                cur.execute("INSERT INTO user_stats (tg_id, xp, streak, last_daily) VALUES (?, 0, 0, 0)", (uid,))
                last_daily, xp, streak = 0, 0, 0
            else:
                last_daily, xp, streak = row
            
            # 检查是否是同一天 (简单的按日期检查)
            # 这里简单用 20小时冷却，或者用日期字符串对比
            # 咱们用日期字符串对比最准
            last_date = time.strftime("%Y-%m-%d", time.localtime(last_daily))
            today_date = time.strftime("%Y-%m-%d", time.localtime(now))
            
            if last_date == today_date:
                await update.message.reply_text("🔮 你今天已经祈福过了，贪心会让魔力反噬哦！\n(明天再来吧)")
                return

            # 2. 随机运势
            fortune_name, min_xp, max_xp, comment = random.choice(FORTUNES)
            
            # 连签奖励
            streak += 1
            bonus = min(streak * 10, 200) # 每天增加10，上限200
            
            # 基础奖励
            base_reward = random.randint(min_xp, max_xp)
            total_reward = base_reward + bonus
            
            # 3. 写入数据库
            cur.execute("UPDATE user_stats SET xp = xp + ?, streak = ?, last_daily = ? WHERE tg_id=?", 
                        (total_reward, streak, now, uid))
            conn.commit()

            # 4. 发送结果
            msg = (
                f"📅 <b>{user.first_name} 的今日运势</b>\n\n"
                f"🏷 运势: <b>{fortune_name}</b>\n"
                f"💰 获得: <b>{base_reward}</b> + 连签 <b>{bonus}</b> = <b>{total_reward} 🌸</b>\n"
                f"🔥 连签: <b>{streak} 天</b>\n"
                f"💬 <i>“{comment}”</i>"
            )
            await update.message.reply_html(msg)

    app.add_handler(CommandHandler(["daily", "checkin", "sign"], daily))
