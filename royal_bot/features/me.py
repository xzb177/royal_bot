# -*- coding: utf-8 -*-
import sqlite3
from telegram.ext import CommandHandler

def _get_level_title(xp):
    if xp >= 20000: return "👸 绝美公主"
    if xp >= 8000:  return "🧚‍♀️ 梦幻精灵"
    if xp >= 2000:  return "🎀 甜心宝贝"
    if xp >= 500:   return "🌸 可爱萌新"
    return "🥚 迷糊小蛋"

def get_conn(path):
    return sqlite3.connect(path, check_same_thread=False)

def register(app, ctx):
    cfg = ctx["cfg"]
    ui = ctx["ui"]
    db_path = cfg.DB_FILE

    async def me(update, context):
        u = update.effective_user
        uid = u.id

        # 默认数据
        xp, streak = 0, 0
        w_count, l_count = 0, 0
        emby_account = "未绑定"
        active_title = "(无)"
        counts = {'LEGENDARY': 0, 'EPIC': 0, 'RARE': 0, 'COMMON': 0}
        identity_status = "👻 游荡幽灵 (未绑定)"

        try:
            with get_conn(db_path) as conn:
                cur = conn.cursor()
                try: cur.execute("ALTER TABLE user_stats ADD COLUMN duels_lost INTEGER DEFAULT 0")
                except: pass

                cur.execute("SELECT xp, streak, duels_won, duels_lost FROM user_stats WHERE tg_id=?", (uid,))
                row = cur.fetchone()
                if row: xp, streak, w_count, l_count = row
                if not w_count: w_count = 0
                if not l_count: l_count = 0
                
                cur.execute("SELECT emby_id, is_vip FROM bindings WHERE tg_id=?", (uid,))
                b_row = cur.fetchone()
                if b_row:
                    emby_account = b_row[0]
                    is_vip = b_row[1]
                    identity_status = "💎 圣殿契约者 (VIP)" if is_vip == 1 else "📜 见习魔法师 (普通)"

                try:
                    cur.execute("SELECT active_title FROM user_cosmetics WHERE tg_id=?", (uid,))
                    t_row = cur.fetchone()
                    if t_row: active_title = t_row[0]
                except: pass

                try:
                    cur.execute("SELECT rarity, COUNT(*) FROM user_posters WHERE user_id=? GROUP BY rarity", (uid,))
                    for rarity, count in cur.fetchall():
                        counts[rarity] = count
                except: pass

        except Exception as e:
            await update.effective_message.reply_text(f"💦 面板卡住了: {e}")
            return

        total_duels = w_count + l_count
        win_rate = int((w_count / total_duels) * 100) if total_duels > 0 else 0
        rate_str = f"{win_rate}%" if total_duels > 0 else "0% (暂无战绩)"

        lines = [
            f"👤 <b>{u.first_name} 的魔法档案</b>",
            "",
            f"🌟 <b>资质认证: {identity_status}</b>",
            f"📺 绑定账号: <code>{emby_account}</code>",
            "",
            f"🏷️ 等级: <b>{_get_level_title(xp)}</b>",
            f"👑 称号: <b>{active_title}</b>",
            "",
            f"🌸 心愿值: <b>{xp}</b>",
            f"📅 连续祈愿: <b>{streak} 天</b>",
            "",
            "⚔️ <b>切磋战绩</b>",
            f"🏆 胜场: <b>{w_count}</b>   🤕 败场: <b>{l_count}</b>",
            f"📊 胜率: <b>{rate_str}</b>",
            "",
            "🎒 <b>收藏袋</b>",
            f"🌟 SSR: {counts.get('LEGENDARY',0)}   💖 SR: {counts.get('EPIC',0)}",
            f"🍬 R: {counts.get('RARE',0)}     🍃 N: {counts.get('COMMON',0)}",
        ]
        
        # === 发送消息 ===
        sent_msg = await update.effective_message.reply_html(ui.panel("✨ 您的专属名片", lines))
        
        # === 🧨 启动自毁 (如果清洁工存在) ===
        cleaner = context.application.bot_data.get("msg_cleaner")
        if cleaner:
            await cleaner(sent_msg)

    app.add_handler(CommandHandler("me", me))
