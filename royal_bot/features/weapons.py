# -*- coding: utf-8 -*-
import time
from telegram.ext import CommandHandler

SHOP = [
    ("rose", "🌹 玫瑰匕首", 300),
    ("card", "🃏 赌徒扑克牌", 500),
    ("crown", "👑 会所皇冠", 1200),
    ("dragon", "🐉 龙纹战刃", 3000),
]

def register(app, ctx):
    ui = ctx["ui"]
    db = ctx["db"]

    async def weapons(update, context):
        uid = update.effective_user.id
        args = [a.strip().lower() for a in (context.args or [])]

        if args and args[0] in ("mine","me","my"):
            rows = await db.list_weapons(uid)
            if not rows:
                await update.effective_message.reply_html(ui.panel("🗡️ 武器库", ["你还没有武器～去 /weapons buy xxx 购入 😎"]))
                return
            lines = [f"• {name} × <b>{qty}</b>" for _, name, qty in rows]
            await update.effective_message.reply_html(ui.panel("🗡️ 我的武器库", lines, "有武器才有排面 😎"))
            return

        if args and args[0] == "buy":
            if len(args) < 2:
                await update.effective_message.reply_html(ui.panel("🗡️ 购入", ["用法：<code>/weapons buy crown</code>"]))
                return
            wid = args[1]
            hit = next((x for x in SHOP if x[0] == wid), None)
            if not hit:
                await update.effective_message.reply_html(ui.panel("🗡️ 购入失败", ["武器不存在，先 /weapons 看列表"]))
                return
            weapon_id, weapon_name, price = hit

            xp, *_ = await db.get_user(uid)
            if xp < price:
                await update.effective_message.reply_html(ui.panel("🗡️ 余额不足", [ui.kv("需要", f"{price} XP"), ui.kv("当前", f"{xp} XP")], "先聊天涨点 XP 😎"))
                return

            await db.add_xp(uid, -price)
            await db.add_weapon(uid, weapon_id, weapon_name, 1, int(time.time()))
            await update.effective_message.reply_html(ui.panel("🗡️ 购入成功", [f"已购入：<b>{weapon_name}</b>", ui.kv("花费", f"{price} XP")], "老板排面++ 😎"))
            return

        # 默认：展示商店
        lines = ["• <b>/weapons buy 武器ID</b> 购入（纯装饰、排面系统）", "• <b>/weapons mine</b> 查看我的武器", "• ✅ <b>决斗联动</b>：主武器会触发不同击杀台词（不影响胜率）", ""]
        for wid, name, price in SHOP:
            lines.append(f"• <code>{wid}</code>  {name}  —  <b>{price} XP</b>")
        await update.effective_message.reply_html(ui.panel("🗡️ 武器库（商店）", lines, "有些东西，买的是排面 😎"))

    app.add_handler(CommandHandler("weapons", weapons))
