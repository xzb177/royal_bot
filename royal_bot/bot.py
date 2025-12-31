# -*- coding: utf-8 -*-
import logging, asyncio
from telegram.ext import ApplicationBuilder, Defaults, CallbackQueryHandler
from .config import load_config
from .db import DB
from .emby import Emby
from .ui import UI
from .loader import load_features
from telegram.constants import ParseMode

# 核心按钮响应函数（直接内嵌，防止加载失败）
async def on_button_click(update, context):
    query = update.callback_query
    if query.data == "start_pray":
        await query.answer()
        await query.edit_message_text("✅ <b>核心驱动已激活：祈愿魔法启动中...</b>", parse_mode="HTML")

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(message)s")
    cfg = load_config()
    db = DB(cfg.DB_FILE)
    emby = Emby(cfg.EMBY_URL, cfg.EMBY_API_KEY, verify_ssl=cfg.EMBY_VERIFY_SSL)
    ui = UI()
    
    app = ApplicationBuilder().token(cfg.BOT_TOKEN).build()
    app.bot_data["ctx"] = {"cfg": cfg, "db": db, "emby": emby, "ui": ui}
    
    # 在主程序层面抢先注册按钮监听（优先级最高）
    app.add_handler(CallbackQueryHandler(on_button_click, pattern="^start_pray"))
    
    loop = asyncio.get_event_loop()
    loop.run_until_complete(db.init())
    
    # 加载其余 36 个功能模块
    load_features(app, app.bot_data["ctx"], [
        "royal_bot.features.common", "royal_bot.features.push", "royal_bot.features.posters",
        "royal_bot.features.daily", "royal_bot.features.status", "royal_bot.features.me"
    ])
    
    logging.info("👑 核心引擎已强行拉起")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
