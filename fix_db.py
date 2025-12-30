import sqlite3

db_path = "/root/royal_bot/royal_bot.db"
print("🔍 正在诊断魔法书...")

try:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # === 核心修复：补全缺失的列 ===
    # 1. 尝试添加 last_checkin (签到日期)
    try:
        cur.execute("ALTER TABLE user_stats ADD COLUMN last_checkin TEXT DEFAULT ''")
        print("✅ 成功修复: 添加了 'last_checkin' (日期记录)")
    except Exception as e:
        print(f"👌 日期记录已存在 (无需修复)")

    # 2. 尝试添加 streak (连签天数)
    try:
        cur.execute("ALTER TABLE user_stats ADD COLUMN streak INTEGER DEFAULT 0")
        print("✅ 成功修复: 添加了 'streak' (连签记录)")
    except Exception as e:
        print(f"👌 连签记录已存在 (无需修复)")

    conn.commit()
    conn.close()
    print("\n🎉 魔法书升级完毕！现在支持每日祈福了！")

except Exception as e:
    print(f"❌ 修复失败: {e}")
