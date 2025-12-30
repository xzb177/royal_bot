import sqlite3

db_path = "/root/royal_bot/royal_bot.db"
print("🔍 正在改造魔法契约书...")

try:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 尝试给 bindings 表加个 is_vip 列，默认是 0 (普通)
    try:
        cur.execute("ALTER TABLE bindings ADD COLUMN is_vip INTEGER DEFAULT 0")
        print("✅ 成功升级: 现在契约书可以记录 VIP 身份了！")
    except Exception as e:
        print(f"👌 契约书已经是最新版了 (无需修复)")

    conn.commit()
    conn.close()

except Exception as e:
    print(f"❌ 升级失败: {e}")
