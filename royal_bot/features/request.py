# -*- coding: utf-8 -*-
from telegram.ext import CommandHandler

# 读取管理员 ID (和审核功能共用一个文件)
ADMIN_FILE = "/root/royal_bot/.admin_id"

def get_admin_id():
    try:
        with open(ADMIN_FILE, "r") as f:
            return int(f.read().strip())
    except:
        return None

def register(app, ctx):
    ui = ctx["ui"]

    async def request(update, context):
        user = update.effective_user
        
        # 1. 检查有没有写内容
        if not context.args:
            await update.message.reply_text("🎋 <b>许愿池</b>\n\n请告诉我想看什么，例如：\n<code>/request 哈利波特与魔法石</code>", parse_mode="HTML")
            return

        # 把用户输入的愿望拼起来
        wish_content = " ".join(context.args)

        # 2. 回复用户 (魔法风)
        lines = [
            f"🎋 <b>{user.first_name} 的心愿</b>",
            "",
            f"✨ 愿望内容:",
            f"<b>「 {wish_content} 」</b>",
            "",
            "🕊️ <i>信鸽已经起飞，正在飞往管理员的城堡...</i>",
            "<i>(请耐心等待愿望实现哦)</i>"
        ]
        await update.effective_message.reply_html(ui.panel("✨ 投递成功", lines))
        
        # 3. 真的通知管理员 (如果管理员设置了的话)
        admin_id = get_admin_id()
        if admin_id:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"🎋 <b>收到新的求片许愿！</b>\n\n👤 用户: {user.first_name} (ID: {user.id})\n📝 内容: <b>{wish_content}</b>",
                    parse_mode="HTML"
                )
            except Exception as e:
                # 如果管理员没私聊过机器人，可能会发不出去，但这不影响回复用户
                print(f"无法通知管理员: {e}")

    app.add_handler(CommandHandler(["request", "wish", "add"], request))
