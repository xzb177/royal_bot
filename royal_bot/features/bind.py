# -*- coding: utf-8 -*-
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler
async def bind(u, c):
    user, db = u.effective_user, c.bot_data["ctx"]["db"]
    r = await db.get_user(user.id)
    is_v = True if user.id in [6803708307] else False
    is_b, eid = False, "未找到"
    if r:
        if isinstance(r, dict): eid = str(r.get("emby_id", "未找到")); is_b = True
        elif isinstance(r, (tuple, list)):
            # 智能找回：跳过数字 ID，寻找真正的字符串账号名
            for item in r:
                if isinstance(item, str) and len(item) > 1 and not item.isdigit():
                    eid = item; is_b = True; break
            if not is_b and len(r) > 0: eid = str(r[-1]); is_b = True
