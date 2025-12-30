# -*- coding: utf-8 -*-
import sqlite3
from telegram.ext import CommandHandler

def get_conn(path):
    return sqlite3.connect(path, check_same_thread=False)

def register(app, ctx):
    cfg = ctx["cfg"]
    ui = ctx["ui"]
    db_path = cfg.DB_FILE

    async def wall(update, context):
        uid = update.effective_user.id
        
        with get_conn(db_path) as conn:
            # 查一下最近获得的 10 张卡
            # 确保表存在
            try:
                cur = conn.cursor()
                cur.execute("SELECT item_name, rarity FROM user_posters WHERE user_id=? ORDER BY rowid DESC LIMIT 15", (uid,))
                rows = cur.fetchall()
                
                # 统计总数
                cur.execute("SELECT rarity, COUNT(*) FROM user_posters WHERE user_id=? GROUP BY rarity", (uid,))
                stats = dict(cur.fetchall())
            except:
                rows = []
                stats = {}

        if not rows:
            await update.message.reply_text("📒 你的手账本还是空的哦，快去 /poster 祈愿第一张卡片吧！")
            return

        # 构造手账页面
        lines = [
            f"📒 <b>{update.effective_user.first_name} 的收藏手账</b>",
            "",
            f"🌟 传说(SSR): {stats.get('SSR', 0)}",
            f"💖 史诗(SR):  {stats.get('SR', 0)}",
            f"🍃 普通/稀有: {stats.get('N', 0) + stats.get('R', 0)}",
            "",
            "<b>🎞️ 最近收录:</b>"
        ]

        for name, rarity in rows:
            icon = "🍃"
            if rarity == "SSR": icon = "🌟"
            elif rarity == "SR": icon = "💖"
            elif rarity == "R": icon = "🍬"
            
            lines.append(f"{icon} {name}")

        lines.append("")
        lines.append("<i>(仅展示最近 15 条)</i>")

        await update.effective_message.reply_html(ui.panel("✨ 收藏册", lines))

    app.add_handler(CommandHandler(["wall", "collection", "bag"], wall))
