# -*- coding: utf-8 -*-
import html
from datetime import datetime, timezone, timedelta

from telegram.ext import CommandHandler

BJ = timezone(timedelta(hours=8))

def _week_id(dt: datetime) -> str:
    iso = dt.isocalendar()  # (year, week, weekday)
    return f"{iso.year}-W{iso.week:02d}"

def _badge(i: int) -> str:
    return {1:"👑", 2:"💎", 3:"🥂"}.get(i, "•")

async def _name_mention(bot, chat_id: int, uid: int) -> str:
    try:
        m = await bot.get_chat_member(chat_id, uid)
        name = m.user.full_name or m.user.first_name or str(uid)
    except Exception:
        name = str(uid)
    name = html.escape(name)
    return f'<a href="tg://user?id={uid}">{name}</a>'

def _points(msgs, spins, posters, duels, bounties) -> int:
    return int(bounties)*10 + int(duels)*3 + int(posters)*2 + int(spins) + int(int(msgs)//10)

def register(app, ctx):
    ui = ctx["ui"]
    db = ctx["db"]
    cfg = ctx["cfg"]

    async def season(update, context):
        now = datetime.now(BJ)
        week = _week_id(now)
        chat_id = update.effective_chat.id

        top = await db.top_weekly(week, limit=10)
        if not top:
            await update.effective_message.reply_html(ui.panel("🏁 周赛季榜", [
                f"本周：<b>{week}</b>",
                "还没有数据～先 /bounty /daily /poster /duel 走起来 😎"
            ]))
            return

        lines = [f"🏁 <b>周赛季榜</b>  ·  本周 <b>{week}</b>", ""]
        for i, (uid, msgs, spins, posters, duels, bounties, pts) in enumerate(top, 1):
            who = await _name_mention(context.bot, chat_id, int(uid))
            lines.append(f"{_badge(i)} {i}. {who}  —  <b>{int(pts)}</b> 分  "
                         f"（悬赏{int(bounties)} / 决斗{int(duels)} / 收藏{int(posters)} / 转盘{int(spins)} / 发言{int(msgs)}）")

        me = update.effective_user.id
        m_msgs, m_spins, m_posters, m_duels, m_bounties = await db.get_weekly_stats(me, week)
        m_pts = _points(m_msgs, m_spins, m_posters, m_duels, m_bounties)
        m_spent = await db.get_weekly_spent(me, week)
        m_avail = max(0, m_pts - m_spent)
        lines += ["", ui.kv("我的本周积分", f"<b>{m_pts}</b> 分"), ui.kv("已消费", f"<b>{m_spent}</b> 分"), ui.kv("可用积分", f"<b>{m_avail}</b> 分"),
                  ui.kv("悬赏领取", f"<b>{m_bounties}</b>"),
                  ui.kv("决斗胜场", f"<b>{m_duels}</b>"),
                  ui.kv("收藏海报", f"<b>{m_posters}</b>"),
                  ui.kv("转盘次数", f"<b>{m_spins}</b>"),
                  ui.kv("发言次数", f"<b>{m_msgs}</b>")]

        await update.effective_message.reply_html(ui.panel("🏁 周赛季榜", lines, "会所周赛季：拼的是稳定输出 😎"))

    async def weekly_rollover_job(context):
        # 每天跑一次：检测跨周后结算上周前三并公告（只公告一次）
        now = datetime.now(BJ)
        this_week = _week_id(now)
        last_week = await db.get_state("season_week_current")
        if not last_week:
            await db.set_state("season_week_current", this_week)
            return
        if last_week == this_week:
            return

        # 发生跨周：结算 last_week
        top = await db.top_weekly(last_week, limit=3)
        if not top:
            await db.set_state("season_week_current", this_week)
            return

        # 发送到群：优先 PUSH_GROUP_ID，否则 GROUP_ID，否则不发
        target_chat = getattr(cfg, "PUSH_GROUP_ID", None) or getattr(cfg, "GROUP_ID", None)
        if not target_chat:
            await db.set_state("season_week_current", this_week)
            return

        lines = [f"🏁 <b>周赛季结算</b>  ·  上周 <b>{last_week}</b>", ""]
        for i, (uid, msgs, spins, posters, duels, bounties, pts) in enumerate(top, 1):
            who = await _name_mention(context.bot, int(target_chat), int(uid))
            lines.append(f"{_badge(i)} {i}. {who}  —  <b>{int(pts)}</b> 分")

        lines += ["", "🎉 恭喜上周前三老板！本周继续卷起来 😎"]
        text = ui.panel("🏁 周赛季结算公告", lines)

        try:
            await context.bot.send_message(chat_id=int(target_chat), text=text, parse_mode="HTML")
        except Exception:
            pass

        await db.set_state("season_week_current", this_week)

    # /season 命令
    app.add_handler(CommandHandler("season", season))

    # 定时任务：每天 00:05（北京时间）检查跨周
    # PTB job_queue 用 UTC，所以我们用 UTC 时间换算：北京时间 00:05 = UTC 前一天 16:05
    # 为简单稳健：每 24h 跑一次，首次在“接下来 1 分钟”启动，然后内部用 BJ 判断跨周（不会重复公告）
    try:
        app.job_queue.run_repeating(weekly_rollover_job, interval=24*60*60, first=60)
    except Exception:
        # 没有 job_queue 也没关系：用户调用 /season 时依然能看到本周榜
        pass
