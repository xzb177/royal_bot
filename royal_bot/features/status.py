# -*- coding: utf-8 -*-
import aiohttp
from telegram.ext import CommandHandler

# === ⚔️ 必杀技：硬核直连版 ===
REAL_URL = "https://emby.oceancloud.asia:443"
REAL_KEY = "7382fe6c3d774f60b5b8d5a50c82aad1"

def register(app, ctx):
    ui = ctx["ui"]

    async def status(update, context):
        sent_msg = None # 记录发出的消息
        try:
            async with aiohttp.ClientSession() as session:
                target = f"{REAL_URL}/emby/Sessions?api_key={REAL_KEY}"
                
                async with session.get(target, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        sessions = data if isinstance(data, list) else []
                        playing = [s for s in sessions if s.get("NowPlayingItem")]
                        count = len(playing)
                        
                        lines = [
                            f"🔮 <b>Emby 魔法水晶球</b>",
                            "",
                            f"✨ 正在观影: <b>{count} 人</b>",
                            f"✅ 状态: <b>{resp.status} (在线)</b>",
                            "",
                            "<i>魔法能量充盈！⚡️</i>"
                        ]
                        sent_msg = await update.effective_message.reply_html(ui.panel("🔮 状态占卜", lines))
                    else:
                        sent_msg = await update.effective_message.reply_text(f"💔 连上了，但是被拒之门外 (状态码 {resp.status})")

        except Exception as e:
            sent_msg = await update.effective_message.reply_text(f"💥 水晶球破裂了！无法连接: {e}")

        # === 🧨 启动自毁 ===
        cleaner = context.application.bot_data.get("msg_cleaner")
        if cleaner and sent_msg:
            await cleaner(sent_msg)

    app.add_handler(CommandHandler("status", status))
