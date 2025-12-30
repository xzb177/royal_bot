# -*- coding: utf-8 -*-
import os
import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

async def bind_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.strip()
    
    # 1. 解析指令
    parts = msg.split()
    if len(parts) < 2:
        await update.message.reply_text("💡 使用方法：\n发送 `/bind 您的Emby账号名`")
        return

    emby_name = parts[1]
    
    # 2. 获取配置
    base_url = os.getenv("REAL_URL")
    api_key = os.getenv("REAL_KEY")
    
    if not base_url or not api_key:
        await update.message.reply_text("⚠️ 机器人配置缺失，请联系管理员。")
        return

    async with aiohttp.ClientSession() as session:
        # 3. 查找用户
        url = f"{base_url}/emby/Users?api_key={api_key}"
        async with session.get(url) as resp:
            if resp.status != 200:
                await update.message.reply_text("❌ 无法连接 Emby，请稍后再试。")
                return
            
            users = await resp.json()
            # 模糊匹配 (忽略大小写)
            target_user = next((u for u in users if u['Name'].lower() == emby_name.lower()), None)
            
            if not target_user:
                await update.message.reply_text(f"❌ 找不到账号：{emby_name}\n请检查拼写是否正确~")
                return

            # ==========================================
            # 🕵️‍♂️ 核心：查面板资质 (Emby 管理员权限)
            # ==========================================
            # 获取用户详细权限策略
            user_id = target_user['Id']
            is_vip = False
            
            # 如果 Policy 里的 IsAdministrator 是 True，他就是那个 VIP
            if target_user.get("Policy", {}).get("IsAdministrator"):
                is_vip = True
            else:
                # 双重保险：有时候简略信息不带 Policy，查一下详情
                detail_url = f"{base_url}/emby/Users/{user_id}?api_key={api_key}"
                async with session.get(detail_url) as d_resp:
                    if d_resp.status == 200:
                        detail = await d_resp.json()
                        if detail.get("Policy", {}).get("IsAdministrator"):
                            is_vip = True

            # ==========================================
            # 🥺 核心：粘人精文案 (情绪价值拉满)
            # ==========================================
            if is_vip:
                # 触发专属撒娇 + 圣殿契约者认证
                reply_text = (
                    f"✨ <b>身份核验通过：尊贵「圣殿契约者」权限！</b>\n"
                    f"━━━━━━━━━━━━━━━━\n\n"
                    f"呜哇！真的是您吗？！😳 <b>{target_user['Name']}</b> ？！\n\n"
                    f"我...我以为那份白名单只是传说，没想到真的有人能点亮它！\n"
                    f"( >﹏< ) 怎...怎么办，我有点紧张... CPU 都要烧坏了...\n\n"
                    f"听好了哦，别的用户只能看普通电影，但您可以 <b>彻底拥有我</b>。\n"
                    f"无论多晚，无论多大的 4K 原盘，只要您想看，我都会第一时间捧到您面前！\n\n"
                    f"<b>👉 您要是敢去别的 Emby 服，我会哭给你看的！</b>\n"
                    f"真的会哭的！把服务器电容哭爆那种！🥺🥺🥺"
                )
            else:
                # 普通用户回复
                reply_text = (
                    f"✅ <b>绑定成功！</b>\n\n"
                    f"欢迎您，<b>{target_user['Name']}</b>。\n"
                    f"您的账号已关联。您可以发送 /daily 领取今日份的运势哦~ ☁️"
                )

            await update.message.reply_text(reply_text, parse_mode="HTML")
