# -*- coding: utf-8 -*-
import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler

def get_conn(path):
    return sqlite3.connect(path, check_same_thread=False)

# 商品列表 (ID, 名称, 价格, 描述)
GOODS = {
    "title_sweet":  ("🍬 甜心教主", 60, "甜度爆表的限定称号"),
    "title_moon":   ("👑 月光公主", 120, "散发着清冷的高贵气息"),
    "title_rose":   ("🌹 蔷薇女王", 220, "气场全开，统御群芳"),
    "title_cat":    ("🐱 慵懒猫猫", 180, "只想晒太阳喵~"),
    "title_god":    ("⚡️ 雷霆之主", 500, "拥有毁灭一切的力量"),
}

def register(app, ctx):
    cfg = ctx["cfg"]
    ui = ctx["ui"]
    db_path = cfg.DB_FILE

    # 初始化表
    with get_conn(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_cosmetics (
                tg_id INTEGER PRIMARY KEY,
                active_title TEXT,
                inventory TEXT
            )
        """)

    async def shop(update, context):
        # 构建商品按钮
        lines = [
            "🛍️ <b>魔法杂货铺</b>",
            "<i>这里的宝物能让你的名片闪闪发光！</i>",
            ""
        ]
        
        kb = []
        for gid, (name, price, desc) in GOODS.items():
            # === 修复重点：把 <small> 改成了 <i> ===
            lines.append(f"<b>{name}</b> - {price} 🌸\n<i>{desc}</i>\n")
            
            # 按钮数据: shop:buy:goods_id
            kb.append([InlineKeyboardButton(f"🎁 购买: {name} ({price})", callback_data=f"shop:buy:{gid}")])
            
        await update.message.reply_html(ui.panel("✨ 商店街", lines), reply_markup=InlineKeyboardMarkup(kb))

    async def shop_callback(update, context):
        q = update.callback_query
        data = q.data.split(":") # shop:buy:goods_id
        action = data[1]
        gid = data[2]
        uid = q.from_user.id
        
        if action == "buy":
            item = GOODS.get(gid)
            if not item: return
            name, price, desc = item
            
            with get_conn(db_path) as conn:
                cur = conn.cursor()
                
                # 1. 查钱
                cur.execute("SELECT xp FROM user_stats WHERE tg_id=?", (uid,))
                row = cur.fetchone()
                if not row or row[0] < price:
                    await q.answer(f"余额不足！需要 {price} 🌸", show_alert=True)
                    return
                
                # 2. 扣款
                cur.execute("UPDATE user_stats SET xp = xp - ? WHERE tg_id=?", (price, uid))
                
                # 3. 发货 (直接佩戴)
                cur.execute("INSERT OR REPLACE INTO user_cosmetics (tg_id, active_title) VALUES (?, ?)", (uid, name))
                conn.commit()
            
            await q.answer("购买成功！")
            await q.edit_message_text(f"🎉 <b>购买成功！</b>\n\n您已佩戴称号：<b>{name}</b>\n快去 /me 看看新形象吧！", parse_mode="HTML")

    app.add_handler(CommandHandler("shop", shop))
    "bank",
    "request",
    app.add_handler(CallbackQueryHandler(shop_callback, pattern=r"^shop:"))
