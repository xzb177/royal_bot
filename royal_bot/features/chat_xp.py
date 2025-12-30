# -*- coding: utf-8 -*-
import sqlite3
import time
import random
from telegram.ext import MessageHandler, filters

# === ⚙️ 配置 ===
COOLDOWN = 60       # 冷却时间：每 60 秒只能获得一次心愿值 (防刷屏)
MIN_XP = 1          # 最小奖励
MAX_XP = 3          # 最大奖励
LUCKY_RATE = 100    # 幸运掉落概率 (1/100)，触发时会说话

def get_conn(path):
    return sqlite3.connect(path, check_same_thread=False)

def register(app, ctx):
    cfg = ctx["cfg"]
    db_path = cfg.DB_FILE
    
    # 内存缓存：记录每个人上次说话的时间 {user_id: timestamp}
    # 这样不需要每次都读数据库，速度快
    LAST_TALK = {}

    async def collect_stardust(update, context):
        if not update.effective_user or update.effective_user.is_bot:
            return

        uid = update.effective_user.id
        now = int(time.time())
        today = time.strftime("%Y-%m-%d", time.localtime(now))
        
        # 1. 检查冷却 (是不是说话太快了)
        last_time = LAST_TALK.get(uid, 0)
        if now - last_time < COOLDOWN:
            return # 还在冷却中，不给钱，但要计入发言数(任务用)
        
        LAST_TALK[uid] = now # 更新时间

        # 2. 计算奖励
        xp_gain = random.randint(MIN_XP, MAX_XP)
        
        # 3. 写入数据库 (核心逻辑)
        try:
            with get_conn(db_path) as conn:
                cur = conn.cursor()
                
                # A. 增加总资产 (user_stats)
                # 先尝试更新，如果没这人就插入
                cur.execute("UPDATE user_stats SET xp = xp + ? WHERE tg_id=?", (xp_gain, uid))
                if cur.rowcount == 0:
                    cur.execute("INSERT INTO user_stats (tg_id, xp) VALUES (?, ?)", (uid, xp_gain))
                
                # B. 更新今日任务统计 (user_daily_stats) - 用于 /bounty
                # 尝试插入今日记录(如果不存在)，然后 msgs + 1
                cur.execute("INSERT OR IGNORE INTO user_daily_stats (tg_id, date) VALUES (?, ?)", (uid, today))
                cur.execute("UPDATE user_daily_stats SET msgs = msgs + 1 WHERE tg_id=? AND date=?", (uid, today))
                
                conn.commit()
                
            # 4. 幸运掉落彩蛋 (增加互动感)
            # 只有 1% 的概率触发，给用户一个小惊喜
            if random.randint(1, LUCKY_RATE) == 1:
                bonus = 20
                with get_conn(db_path) as conn:
                    conn.execute("UPDATE user_stats SET xp = xp + ? WHERE tg_id=?", (bonus, uid))
                    conn.commit()
                
                flavor = random.choice([
                    "✨ 走路捡到了亮晶晶的星尘碎片！",
                    "🧚‍♀️ 一只魔法蝴蝶停在了你的肩膀上~",
                    "🌸 空气中突然充满了香甜的气息！",
                    "💫 灵感涌现！"
                ])
                
                # 引用用户的消息回复
                await update.message.reply_html(f"{flavor}\n(意外获得 <b>+{bonus} 心愿值</b>)")

        except Exception as e:
            # 聊天监听器如果出错，千万不能报错刷屏，悄悄记录即可
            print(f"Chat XP Error: {e}")

    # 监听所有文本消息 (排除命令)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, collect_stardust))
