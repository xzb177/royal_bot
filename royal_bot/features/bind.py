# -*- coding: utf-8 -*-
import sqlite3
import random
import string
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler

# 内存暂存申请
PENDING_REQUESTS = {}
ADMIN_FILE = "/root/royal_bot/.admin_id"

def get_conn(path):
    return sqlite3.connect(path, check_same_thread=False)

def get_admin_id():
    try:
        with open(ADMIN_FILE, "r") as f:
            return int(f.read().strip())
    except:
        return None

def register(app, ctx):
    cfg = ctx["cfg"]
    ui = ctx["ui"]
    db_path = cfg.DB_FILE

    # === 管理员认证 ===
    async def set_admin(update, context):
        uid = update.effective_user.id
        with open(ADMIN_FILE, "w") as f:
            f.write(str(uid))
        await update.message.reply_text("👑 <b>会长认证成功！</b>\n以后审核大权就交给您了！")

    # === 用户申请 ===
    async def bind_request(update, context):
        user = update.effective_user
        if not context.args:
            await update.message.reply_text("📜 <b>格式错误</b>\n请填写账号，例如：<code>/bindme myname</code>", parse_mode="HTML")
            return

        emby_name = context.args[0]
        admin_id = get_admin_id()
        if not admin_id:
            await update.message.reply_text("⚠️ 管理员未上班 (未设置 ID)")
            return

        req_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        PENDING_REQUESTS[req_id] = {"uid": user.id, "username": user.first_name, "emby": emby_name}

        # 通知用户
        await update.message.reply_html(
            f"📨 <b>申请已提交</b>\n⏳ 账号 <b>{emby_name}</b> 正在等待魔法议会审核..."
        )

        # === ✨ 重点改动：管理员收到 3 个按钮 ===
        admin_lines = [
            "📝 <b>新的契约申请</b>",
            "",
            f"👤 申请人: <b>{user.first_name}</b>",
            f"📺 Emby账号: <code>{emby_name}</code>",
            "",
            "<i>请选择授予的身份等级：</i>"
        ]
        
        # 按钮布局：第一行两个批准，第二行一个驳回
        kb = [
            [
                InlineKeyboardButton("✅ 批准 (普通)", callback_data=f"audit:yes:{req_id}"),
                InlineKeyboardButton("💎 批准 (圣殿VIP)", callback_data=f"audit:vip:{req_id}")
            ],
            [
                InlineKeyboardButton("🚫 驳回申请", callback_data=f"audit:no:{req_id}")
            ]
        ]
        
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=ui.panel("⚖️ 身份裁决", admin_lines),
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode="HTML"
            )
        except:
            await update.message.reply_text("💦 无法联系管理员，请确认管理员已启动机器人。")

    # === 审核回调 ===
    async def audit_callback(update, context):
        q = update.callback_query
        data = q.data.split(":") 
        action = data[1] # yes / vip / no
        req_id = data[2]
        
        req = PENDING_REQUESTS.get(req_id)
        if not req:
            await q.answer("⚠️ 申请已失效", show_alert=True)
            await q.edit_message_reply_markup(None)
            return

        uid = req["uid"]
        emby_name = req["emby"]
        user_name = req["username"]

        if action in ["yes", "vip"]:
            # === 同意 ===
            is_vip = 1 if action == "vip" else 0
            vip_text = "💎 圣殿契约者 (VIP)" if is_vip else "📜 见习魔法师"
            
            with get_conn(db_path) as conn:
                # 写入 VIP 状态
                conn.execute("INSERT OR REPLACE INTO bindings (tg_id, emby_id, is_vip, created_at) VALUES (?, ?, ?, strftime('%s','now'))", (uid, emby_name, is_vip))
                conn.commit()
            
            # 修改管理员消息
            await q.edit_message_text(f"✅ <b>已批准 ({vip_text})</b>\n👤 {user_name} ↔️ {emby_name}", parse_mode="HTML")
            
            # 通知用户
            msg = f"🎉 <b>审核通过！</b>\n\n您的账号 <b>{emby_name}</b> 已绑定！\n"
            if is_vip:
                msg += "💎 <b>恭喜！您被破格授予「圣殿契约者」尊贵身份！</b>"
            else:
                msg += "📜 身份认证为：<b>见习魔法师</b>"
                
            try:
                await context.bot.send_message(chat_id=uid, text=msg, parse_mode="HTML")
            except: pass

        else:
            # === 拒绝 ===
            await q.edit_message_text(f"🚫 <b>已驳回</b>\n👤 {user_name}", parse_mode="HTML")
            try:
                await context.bot.send_message(chat_id=uid, text="💔 <b>审核未通过</b>", parse_mode="HTML")
            except: pass

        del PENDING_REQUESTS[req_id]

    app.add_handler(CommandHandler(["bindme", "bind"], bind_request))
    app.add_handler(CommandHandler(["iamgod", "setadmin"], set_admin))
    app.add_handler(CallbackQueryHandler(audit_callback, pattern=r"^audit:"))
