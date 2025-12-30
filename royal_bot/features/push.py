# -*- coding: utf-8 -*-
from telegram.ext import CommandHandler

def register(app, ctx):
    ui = ctx["ui"]
    db = ctx["db"]
    emby = ctx["emby"]
    cfg = ctx["cfg"]

    async def _check_once(bot):
        try:
            item = await emby.latest_item()
        except Exception:
            item = None
        if not item or not item.get("Id"):
            return

        item_id = str(item.get("Id"))
        last = await db.get_state("last_push_id")
        if last == item_id:
            return

        await db.set_state("last_push_id", item_id)

        try:
            detail = await emby.item_detail(item_id)
        except Exception:
            detail = item

        name = detail.get("Name") or "Unknown"
        year = detail.get("ProductionYear") or ""
        genres = detail.get("Genres") or []
        g = " | ".join(genres[:3]) if genres else "未知"
        rating = detail.get("CommunityRating")
        r = f"{float(rating):.1f}" if isinstance(rating, (int, float)) else "N/A"

        caption = ui.panel("⚡ NEW ARRIVAL | 入库推送", [
            f"🎬 <b>{name}</b> ({year})",
            ui.kv("类型", f"<b>{g}</b>"),
            ui.kv("评分", f"<b>{r}</b>"),
            "",
            "🍿 已加入影库，老板请享用 😎"
        ])

        target = getattr(cfg, "PUSH_GROUP_ID", None) or getattr(cfg, "GROUP_ID", None)
        if not target:
            return

        try:
            img = await emby.item_primary_image_url(item_id)
            await bot.send_photo(chat_id=int(target), photo=img, caption=caption, parse_mode="HTML")
        except Exception:
            await bot.send_message(chat_id=int(target), text=caption, parse_mode="HTML")

    async def push_now(update, context):
        # 手动触发一次检查（老板调试用）
        await _check_once(context.bot)
        await update.effective_message.reply_html(ui.panel("📣 推送检查", ["已执行一次入库检测 ✅"], "需要我就会推～"))

    # 定时任务：按 cfg.CHECK_INTERVAL 秒运行一次（默认 300）
    try:
        interval = int(getattr(cfg, "CHECK_INTERVAL", 300))
        app.job_queue.run_repeating(lambda c: _check_once(c.bot), interval=interval, first=15)
    except Exception:
        pass

    app.add_handler(CommandHandler("push", push_now))
