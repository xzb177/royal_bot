# -*- coding: utf-8 -*-
import sqlite3
import random
import aiohttp
import time
from telegram.ext import CommandHandler

# === 🔮 硬核配置 ===
REAL_URL = "https://emby.oceancloud.asia:443"
REAL_KEY = "7382fe6c3d774f60b5b8d5a50c82aad1"

RARITY_MAP = [("N", "🍃 普通", 50), ("R", "🍬 稀有", 35), ("SR", "💖 史诗", 12), ("SSR","🌟 传说", 3)]

def get_conn(path): return sqlite3.connect(path, check_same_thread=False)

def get_rarity():
    r = random.randint(1, 100)
    curr = 0
    for code, name, chance in RARITY_MAP:
        curr += chance
        if r <= curr: return code, name
    return "N", "🍃 普通"

# === 🛡️ 核心修复：建表语句 ===
def init_table(conn):
    # 创建标准的 5 列新表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_posters (
            user_id INTEGER, 
            item_id TEXT, 
            item_name TEXT, 
            rarity TEXT, 
            created_at INTEGER
        )
    """)

def register(app, ctx):
    cfg = ctx["cfg"]
    db_path = cfg.DB_FILE

    # 启动时先检查一次建表
    with get_conn(db_path) as conn:
        init_table(conn)

    async def poster(update, context):
        user = update.effective_user
        msg = await update.message.reply_html("🔮 <b>正在汇聚星光...</b>")
        
        # 1. 扣费
        COST = 200
        with get_conn(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT xp FROM user_stats WHERE tg_id=?", (user.id,))
            row = cur.fetchone()
            if not row or row[0] < COST:
                await msg.edit_text(f"💸 魔力不足！需要 {COST} 点。")
                # 没钱的提示也自毁
                cleaner = context.application.bot_data.get("msg_cleaner")
                if cleaner: await cleaner(msg, delay=10)
                return
            cur.execute("UPDATE user_stats SET xp = xp - ? WHERE tg_id=?", (COST, user.id))
            conn.commit()

        try:
            # 2. Emby 抽卡
            async with aiohttp.ClientSession() as session:
                search_url = f"{REAL_URL}/emby/Items?IncludeItemTypes=Movie,Series&Recursive=true&SortBy=Random&Limit=1&Fields=Overview,ProductionYear&api_key={REAL_KEY}"
                async with session.get(search_url, timeout=10) as resp:
                    if resp.status != 200:
                        await msg.edit_text(f"💥 魔法连接中断 {resp.status}")
                        return
                    data = await resp.json()
                    item = data.get("Items", [])[0] if data.get("Items") else None
                    
                    if not item:
                        await msg.edit_text("🍂 档案库里空空如也...")
                        return
                    
                    item_id = item["Id"]
                    item_name = item.get("Name", "未知影片")
                    year = item.get("ProductionYear", "????")
                    rarity_code, rarity_name = get_rarity()

                    img_url = f"{REAL_URL}/emby/Items/{item_id}/Images/Primary?maxHeight=800&maxWidth=600&quality=90"
                    async with session.get(img_url) as img_resp:
                        img_data = await img_resp.read() if img_resp.status == 200 else None

            # 3. 入库 (🛡️ 智能防爆写入)
            with get_conn(db_path) as conn:
                try:
                    # 尝试正常写入
                    conn.execute("""
                        INSERT INTO user_posters (user_id, item_id, item_name, rarity, created_at) 
                        VALUES (?, ?, ?, ?, ?)
                    """, (user.id, item_id, item_name, rarity_code, int(time.time())))
                    conn.commit()
                except sqlite3.OperationalError:
                    # 💥 如果报错（比如列名不对），说明表坏了
                    # ⚡️ 触发自动修复：重建表！
                    print("⚠️ 数据库表结构不匹配，正在自动重建 user_posters 表...")
                    conn.execute("DROP TABLE IF EXISTS user_posters") # 删掉旧表
                    init_table(conn) # 建新表
                    # 重试写入
                    conn.execute("""
                        INSERT INTO user_posters (user_id, item_id, item_name, rarity, created_at) 
                        VALUES (?, ?, ?, ?, ?)
                    """, (user.id, item_id, item_name, rarity_code, int(time.time())))
                    conn.commit()

            # 4. 发送结果
            caption = (f"✨ <b>祈愿成功！</b>\n🎬 <b>{item_name} ({year})</b>\n🌈 稀有度: <b>{rarity_name}</b>\n💰 消耗: {COST} 🌸")

            if img_data:
                final_msg = await update.message.reply_photo(photo=img_data, caption=caption, parse_mode="HTML")
                await msg.delete() 
            else:
                final_msg = await msg.edit_text(caption)

            # 启动自毁
            cleaner = context.application.bot_data.get("msg_cleaner")
            if cleaner:
                await cleaner(final_msg)

        except Exception as e:
            await msg.edit_text(f"💥 祈愿仪式发生了爆炸: {e}")
            # 退钱
            with get_conn(db_path) as conn:
                conn.execute("UPDATE user_stats SET xp = xp + ? WHERE tg_id=?", (COST, user.id))

    app.add_handler(CommandHandler(["poster"], poster))
