# -*- coding: utf-8 -*-
import logging
import asyncio
from telegram.ext import ApplicationBuilder, Defaults

from .config import load_config
from .db import DB
from .emby import Emby
from .ui import UI
from .loader import load_features
from telegram.constants import ParseMode


def build_defaults():
    try:
        from telegram import LinkPreviewOptions
        return Defaults(
            parse_mode=ParseMode.HTML,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    except Exception:
        return Defaults(
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )


log = logging.getLogger("royal.bot")

DEFAULT_MODULES = [
    "royal_bot.features.common",
    "royal_bot.features.binding",
    "royal_bot.features.doctor",
    "royal_bot.features.status",
    "royal_bot.features.me",
    "royal_bot.features.xp",
    "royal_bot.features.daily",
    "royal_bot.features.spin",
    "royal_bot.features.bounty",
    "royal_bot.features.season",
    "royal_bot.features.shop",
    "royal_bot.features.bind",
    "royal_bot.features.libs",
    "royal_bot.features.duel",
    "royal_bot.features.poster",
    "royal_bot.features.wall",
    "royal_bot.features.posters",
    "royal_bot.features.pity",
    "royal_bot.features.weapons",
    "royal_bot.features.hall",
    "royal_bot.features.winrate",
    "royal_bot.features.myrank",
    "royal_bot.features.push",
]

async def on_error(update, context):
    log.exception("Unhandled exception", exc_info=context.error)

async def _bootstrap(app, ctx):
    await ctx["db"].init()

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    cfg = load_config()
    db = DB(cfg.DB_FILE)
    emby = Emby(cfg.EMBY_URL, cfg.EMBY_API_KEY, verify_ssl=cfg.EMBY_VERIFY_SSL, lib_whitelist=cfg.EMBY_LIBRARY_WHITELIST)
    ui = UI()

    ctx = {
        "cfg": cfg,
        "db": db,
        "emby": emby,
        "ui": ui,
    }

    app = ApplicationBuilder().token(cfg.BOT_TOKEN).build()
    app.add_error_handler(on_error)

    # 把 ctx 放入 bot_data，插件统一从这里拿
    app.bot_data["ctx"] = ctx

    # 启动前初始化 DB
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_bootstrap(app, ctx))

    # 装载插件
    load_features(app, ctx, DEFAULT_MODULES)

    log.info("👑 Royal Bot｜皇家会所 启动中…")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
