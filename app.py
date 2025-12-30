
import logging, asyncio, os, sys, sqlite3, importlib, pkgutil
from telegram import Update
from telegram.ext import ApplicationBuilder

# === 核心修复点：修正引用路径 ===
# 之前多写了一层 royal_bot，现在改对了
try:
    from royal_bot.migrate import run_migrations
except ImportError:
    # 备用方案：如果还在深层目录
    try:
        from royal_bot.royal_bot.migrate import run_migrations
    except:
        print("⚠️ 警告：无法加载数据库迁移模块，将跳过迁移...")
        run_migrations = lambda db: None

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.getenv("BOT_TOKEN")
DB_FILE = os.getenv("DB_FILE", "/root/royal_bot/royal_bot.db")

async def main():
    print("\n" + "="*40)
    print(">>> 🚀 正在启动：手动修复版 V2 (Manual Mode) <<<")
    print("="*40)

    # 1. 连接数据库
    try:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        run_migrations(conn)
        print(">>> 💾 数据库连接成功")
    except Exception as e:
        print(f"⚠️ 数据库非致命错误: {e}")

    # 2. 构建机器人
    if not TOKEN:
        print("❌ 致命错误: 没有找到 Token！")
        return
    app = ApplicationBuilder().token(TOKEN).build()

    # 3. 扫描功能
    print(">>> 🔍 正在扫描功能文件夹 (Features)...")
    try:
        # 这里也同步修正路径
        import royal_bot.features
        package = royal_bot.features
        prefix = package.__name__ + "."
        
        count = 0
        for _, name, _ in pkgutil.iter_modules(package.__path__, prefix):
            try:
                module = importlib.import_module(name)
                # 尝试各种加载方式
                if hasattr(module, "register"):
                    module.register(app)
                    print(f"   ✅ [挂载] {name.split('.')[-1]}")
                    count += 1
                elif hasattr(module, "setup"):
                    module.setup(app)
                    print(f"   ✅ [挂载] {name.split('.')[-1]}")
                    count += 1
                elif hasattr(module, "handlers"):
                    for handler in module.handlers:
                        app.add_handler(handler)
                    print(f"   ✅ [挂载] {name.split('.')[-1]}")
                    count += 1
            except Exception as e:
                print(f"   ⚠️ 跳过 {name.split('.')[-1]}: {e}")

        print(f"\n>>> 🎉 成功加载 {count} 个功能！")
    except Exception as e:
        print(f"❌ 扫描失败: {e}")

    # 4. 启动
    print(">>> 🚀 系统就绪！正在运行... (请去 Telegram 发 /start)")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
