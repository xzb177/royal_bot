# -*- coding: utf-8 -*-
from telegram.ext import CommandHandler

# 复用 /bounty 的同一个函数
from royal_bot.features.bounty import bounty as _bounty_handler

async def season(update, context):
    return await _bounty_handler(update, context)

def register(app, cfg):
    # group 越小越先执行，避免被其它“文本路由/中文代理”抢走
    app.add_handler(CommandHandler("season", season), group=-999)
