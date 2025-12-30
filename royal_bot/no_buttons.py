from telegram import ReplyKeyboardRemove

def apply_no_buttons(app):
    bot = app.bot

    def _strip(kwargs):
        rm = kwargs.get("reply_markup", None)
        # 允许“移除键盘”，用来清掉历史残留按钮
        if isinstance(rm, ReplyKeyboardRemove):
            return
        if "reply_markup" in kwargs:
            kwargs.pop("reply_markup", None)

    # wrap send_message / edit_message_text / send_photo 等常用出口
    async def wrap_async(fn, *args, **kwargs):
        _strip(kwargs)
        return await fn(*args, **kwargs)

    bot._send_message_orig = bot.send_message
    bot.send_message = lambda *a, **k: wrap_async(bot._send_message_orig, *a, **k)

    bot._edit_message_text_orig = bot.edit_message_text
    bot.edit_message_text = lambda *a, **k: wrap_async(bot._edit_message_text_orig, *a, **k)

    if hasattr(bot, "send_photo"):
        bot._send_photo_orig = bot.send_photo
        bot.send_photo = lambda *a, **k: wrap_async(bot._send_photo_orig, *a, **k)

    if hasattr(bot, "send_document"):
        bot._send_document_orig = bot.send_document
        bot.send_document = lambda *a, **k: wrap_async(bot._send_document_orig, *a, **k)

    if hasattr(bot, "send_video"):
        bot._send_video_orig = bot.send_video
        bot.send_video = lambda *a, **k: wrap_async(bot._send_video_orig, *a, **k)
