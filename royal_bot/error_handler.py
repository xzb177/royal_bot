# -*- coding: utf-8 -*-
import logging

log = logging.getLogger("royal.error")

async def on_error(update, context):
    # 记录真实报错
    log.exception("Unhandled exception", exc_info=context.error)

    # 给用户一个“有反应”的提示（不带按钮）
    try:
        msg = getattr(update, "effective_message", None) if update else None
        if msg:
            await msg.reply_text(
                "呜呜…我刚刚打了个小喷嚏🥺\n"
                "已经把错误记到日志里啦～你再试一次如果还不行就把日志发我💗",
                quote=False
            )
    except Exception:
        pass
