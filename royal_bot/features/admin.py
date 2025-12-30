from telegram import ReplyKeyboardMarkup, KeyboardButton
import re
"""
兼容占位版 admin feature：
先保证插件系统能正常 import，不再报 ModuleNotFoundError。
后续你要我再把旧版 /ban /unban /say /shutup 全量迁进来也可以。
"""

from telegram.ext import CommandHandler

def register(app, ctx):
    async def _admin_stub(update, context):
        await update.message.reply_text("✅ admin 模块已加载（占位版）。需要我把旧版管理命令完整迁移进来就说一声。")

    # 给一个占位命令，便于确认模块已经正常加载
    app.add_handler(CommandHandler("admin", _admin_stub))


# --- AUTO_REQ_BUTTONS_V2: /requests -> tap buttons to send /approve /reject ---
def _kb_from_requests_text(msg: str):
    ids = [int(x) for x in re.findall(r"#(\d+)", msg)]
    if not ids:
        return None
    rows = []
    for rid in ids[:10]:
        rows.append([KeyboardButton(f"/approve {rid}"), KeyboardButton(f"/reject {rid}")])
    rows.append([KeyboardButton("/requests"), KeyboardButton("/menu")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)
# --- /AUTO_REQ_BUTTONS_V2 ---

