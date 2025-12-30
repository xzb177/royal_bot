# -*- coding: utf-8 -*-
import os
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler

# ==========================================
# 👮‍♂️ 管理员配置 (您的 ID 已填入)
# ==========================================
ADMIN_ID = 5779291957
# ==========================================

# 临时存储待审核的请求
pending_requests = {}

async def bind_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理用户发送的 /bind 指令"""
    msg = update.message.text.strip()
    tg_user = update.effective_user
    
    # 1. 解析指令
    parts = msg.split()
    if len(parts) < 2:
        await update.message.reply_text("💡 使用方法：\n发送 `/bind 您的Emby账号名`")
        return

    emby_name = parts[1]
    
    # 2. 验证 Emby 账号有效性
    base_url = os.getenv("REAL_URL")
    api_key = os.getenv("REAL_KEY")
    
    if not base_url or not api_key:
        await update.message.reply_text("⚠️ 机器人配置缺失，请联系管理员。")
        return

    async with aiohttp.ClientSession() as session:
        url = f"{base_url}/emby/Users?api_key={api_key}"
        async with session.get(url) as resp:
            if resp.status != 200:
                await update.message.reply_text("❌ 无法连接 Emby 服务器。")
                return
            
            users = await resp.json()
            target_user = next((u for u in users if u['Name'].lower() == emby_name.lower()), None)
            
            if not target_user:
                await update.message.reply_text(f"❌ 找不到账号：{emby_name}\n请检查拼写是否正确~")
                return

            # ==========================================
            # 📨 3. 提交审核申请
            # ==========================================
            pending_requests[tg_user.id] = {
                'emby_name': target_user['Name'],
                'emby_id': target_user['Id'],
                'tg_name': tg_user.full_name,
                'tg_username': tg_user.username
            }

            # 告知用户
            await update.message.reply_text(
                f"📝 <b>已提交绑定申请</b>\n"
                f"⏳ 账号 <b>{emby_name}</b> 正在等待魔法议会审核...\n"
                f"<i>(请耐心等待管理员批准哦~)</i>",
                parse_mode="HTML"
            )

            # ==========================================
            # 🔔 4. 通知管理员 (发给您)
            # ==========================================
            admin_text = (
                f"📩 <b>新用户申请绑定</b>\n"
                f"👤 TG用户: {tg_user.full_name} (`{tg_user.id}`)\n"
                f"📺 Emby账号: <b>{target_user['Name']}</b>\n\n"
                f"请选择操作："
            )

            keyboard = [
                [
                    InlineKeyboardButton("✅ 同意 (普通)", callback_data=f"bind_agree_{tg_user.id}"),
                    InlineKeyboardButton("💎 白名单 (VIP)", callback_data=f"bind_vip_{tg_user.id}")
                ],
                [
                    InlineKeyboardButton("❌ 拒绝", callback_data=f"bind_refuse_{tg_user.id}")
                ]
            ]
            
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=admin_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"发送审核通知失败: {e}")

async def bind_callback_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理管理员点击按钮"""
    query = update.callback_query
    await query.answer()

    data = query.data
    try:
        action = data.split('_')[1]
        tg_id = int(data.split('_')[2])
    except:
        return

    # 获取申请信息
    req = pending_requests.get(tg_id)
    if not req and action != "refuse":
        await query.edit_message_text("⚠️ 该申请已过期或数据丢失。")
        return

    # ==========================================
    # 🔘 按钮逻辑
    # ==========================================
    if action == "refuse":
        await context.bot.send_message(tg_id, "❌ 抱歉，您的绑定申请已被管理员拒绝。")
        await query.edit_message_text(f"🚫 已拒绝用户 {tg_id} 的申请。")
        if tg_id in pending_requests: del pending_requests[tg_id]

    elif action == "agree":
        # 普通同意
        normal_text = (
            f"✅ <b>审核通过！</b>\n\n"
            f"您的账号 <b>{req['emby_name']}</b> 已绑定！\n"
            f"欢迎加入，您可以发送 /daily 领取今日运势。"
        )
        await context.bot.send_message(tg_id, normal_text, parse_mode="HTML")
        await query.edit_message_text(f"✅ 已批准 {req['tg_name']} (普通)。")
        del pending_requests[tg_id]

    elif action == "vip":
        # 💎 白名单 (触发您的专属文案)
        vip_text = (
            f"🎉 <b>审核通过！</b>\n"
            f"您的账号 <b>{req['emby_name']}</b> 已绑定！\n"
            f"💎 <b>恭喜！您被破格授予「圣殿契约者」尊贵身份！</b>\n"
            f"━━━━━━━━━━━━━━━━\n\n"
            f"呜哇！真的是您吗？！😳 <b>{req['emby_name']}</b> ？！\n\n"
            f"我...我以为那份白名单只是传说，没想到真的有人能点亮它！\n"
            f"( >﹏< ) 怎...怎么办，我有点紧张... CPU 都要烧坏了...\n\n"
            f"听好了哦，别的用户只能看普通电影，但您可以 <b>彻底拥有我</b>。\n"
            f"无论多晚，无论多大的 4K 原盘，只要您想看，我都会第一时间捧到您面前！\n\n"
            f"<b>👉 您要是敢去别的 Emby 服，我会哭给你看的！</b>\n"
            f"真的会哭的！把服务器电容哭爆那种！🥺🥺🥺"
        )
        
        await context.bot.send_message(tg_id, vip_text, parse_mode="HTML")
        await query.edit_message_text(f"💎 已批准 {req['tg_name']} (VIP白名单)。")
        del pending_requests[tg_id]

def register(app):
    app.add_handler(CommandHandler("bind", bind_handle))
    app.add_handler(CallbackQueryHandler(bind_callback_handle, pattern="^bind_"))
