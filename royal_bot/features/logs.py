"""
兼容占位版 logs feature：先保证能 import。
后续可以接入 memlog / sqlite 日志查询、/logs 等。
"""

from telegram.ext import CommandHandler

def register(app, ctx):
    async def _logs_stub(update, context):
        await update.message.reply_text("✅ logs 模块已加载（占位版）。要做 /logs 查询我可以继续加。")

    app.add_handler(CommandHandler("logs", _logs_stub))
