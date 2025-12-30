# -*- coding: utf-8 -*-
import asyncio
from telegram.ext import CommandHandler

# 默认自毁时间 (秒)
DEFAULT_DELETE_TIME = 60

def register(app, ctx):
    # 将配置挂载到全局 bot_data，方便其他插件调用
    if "clean_time" not in app.bot_data:
        app.bot_data["clean_time"] = DEFAULT_DELETE_TIME

    # === 1. 设置自毁时间的命令 ===
    async def set_clean_time(update, context):
        try:
            seconds = int(context.args[0])
            if seconds < 0: raise ValueError
        except:
            await update.message.reply_text("⏱ 格式错误！\n请输入秒数，例如：/cleantime 30\n(输入 0 代表不删除)")
            return

        context.application.bot_data["clean_time"] = seconds
        if seconds == 0:
            await update.message.reply_text("✅ 已关闭【阅后即焚】模式，消息将永久保留。")
        else:
            await update.message.reply_text(f"⏱ 【阅后即焚】已设定：机器人消息将在 <b>{seconds}秒</b> 后自动销毁。", parse_mode="HTML")

    # === 2. 核心：自毁任务 ===
    async def auto_delete(msg, delay=None):
        """其他插件调用这个函数来删除消息"""
        if not msg: return
        
        # 如果没传时间，就读全局配置
        if delay is None:
            delay = app.bot_data.get("clean_time", DEFAULT_DELETE_TIME)
        
        # 0秒不删
        if delay <= 0:
            return

        # 启动后台倒计时
        asyncio.create_task(_delete_task(msg, delay))

    async def _delete_task(msg, delay):
        await asyncio.sleep(delay)
        try:
            await msg.delete()
        except Exception:
            pass # 可能已经被删了，或者没权限，忽略报错

    # 把“删除服务”挂载到 app 上，让别的插件能用
    app.bot_data["msg_cleaner"] = auto_delete

    app.add_handler(CommandHandler(["cleantime", "autoclean"], set_clean_time))
