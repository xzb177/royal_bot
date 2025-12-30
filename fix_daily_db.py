import sqlite3

db_path = "/root/royal_bot/royal_bot.db"
print("🔍 正在升级魔法书 (每日统计页)...")

try:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 建表：user_daily_stats
    # 记录：用户ID, 日期, 发言数, 转盘数, 海报数, 赢的场数
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_daily_stats (
            tg_id INTEGER,
            date TEXT,
            msgs INTEGER DEFAULT 0,
            spins INTEGER DEFAULT 0,
            posters_saved INTEGER DEFAULT 0,
            duels_won INTEGER DEFAULT 0,
            PRIMARY KEY (tg_id, date)
        )
    """)
    print("✅ 成功创建: user_daily_stats (每日任务统计)")

    conn.commit()
    conn.close()
    print("\n🎉 升级完毕！现在可以开始统计发言赚心愿值了！")

except Exception as e:
    print(f"❌ 修复失败: {e}")
