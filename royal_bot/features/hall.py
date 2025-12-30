# -*- coding: utf-8 -*-
import sqlite3
from telegram.ext import CommandHandler

def get_conn(path):
    return sqlite3.connect(path, check_same_thread=False)

def register(app, ctx):
    cfg = ctx["cfg"]
    ui = ctx["ui"]
    db_path = cfg.DB_FILE

    async def hall(update, context):
        with get_conn(db_path) as conn:
            cur = conn.cursor()
            # 获取前 10 名大魔法师
            cur.execute("SELECT tg_id, xp FROM user_stats ORDER BY xp DESC LIMIT 10")
            rows = cur.fetchall()

        lines = [
            "🏆 <b>荣耀圣殿</b>",
            "<i>记载着拥有最强魔力的魔法师们...</i>",
            ""
        ]

        medals = ["🥇", "🥈", "🥉"]
        
        for i, (uid, xp) in enumerate(rows):
            # 尝试获取名字 (需要通过 bot 接口，或者直接不显示名字只显示 ID 掩码，或者如果不涉及隐私可以直接显示)
            # 为了速度，我们这里不实时拉取名字，而是显示 "魔法师 [ID后4位]" 
            # *或者* 如果您希望显示真实名字，需要机器人之前缓存过。
            # 这里用一个简单的技巧：尝试从 chat member 获取，获取不到就用 ID
            
            try:
                # 尝试获取用户对象
                member = await context.bot.get_chat_member(update.effective_chat.id, uid)
                name = member.user.first_name
            except:
                name = f"魔法师 {str(uid)[-4:]}"

            rank_icon = medals[i] if i < 3 else f"{i+1}."
            lines.append(f"{rank_icon} <b>{name}</b> — {xp} 🌸")

        lines.append("")
        lines.append(f"✨ 加油修炼吧，{update.effective_user.first_name}！")
        
        await update.effective_message.reply_html(ui.panel("✨ 魔力排行榜", lines))

    app.add_handler(CommandHandler(["hall", "rank", "top"], hall))
