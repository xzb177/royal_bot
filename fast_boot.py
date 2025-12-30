import os, sqlite3, importlib, pkgutil, asyncio
from telegram.ext import ApplicationBuilder

class Context:
    def __init__(self, db, bot):
        self.db = db
        self.bot = bot
        self.config = self
        self.cfg = self

async def main():
    print(">>> 🚀 极简修复版启动 <<<")
    token = os.getenv("BOT_TOKEN")
    db = os.getenv("DB_FILE", "/root/royal_bot/royal_bot.db")
    app = ApplicationBuilder().token(token).build()
    
    try: conn = sqlite3.connect(db, check_same_thread=False)
    except: conn = None
    
    ctx = Context(conn, app.bot)
    
    import royal_bot.features
    pkg = royal_bot.features
    
    for _, n, _ in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
        try:
            m = importlib.import_module(n)
            if hasattr(m, "register"):
                try: 
                    m.register(app, ctx)
                    print(f"✅ {n.split('.')[-1]} (双参)")
                except: 
                    m.register(app)
                    print(f"✅ {n.split('.')[-1]} (单参)")
            elif hasattr(m, "setup"):
                m.setup(app)
                print(f"✅ {n.split('.')[-1]} (setup)")
        except: pass

    print(">>> 正在连接 Telegram ...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
