# -*- coding: utf-8 -*-
import os
import aiohttp
import asyncio
from telegram.ext import ContextTypes

# ==========================================
# 🎀 哨兵配置 (已自动填好)
# ==========================================

# 1. 消息推送到哪个群？
TARGET_CHAT_ID = -1002306960410

# 2. 哪些媒体库需要推送？(白名单)
WHITELIST = ["电影", "remux电影"]

# 3. 扫描频率 (秒)
CHECK_INTERVAL = 60 

# ==========================================

async def get_library_map(base_url, key):
    """获取所有媒体库的 ID -> Name 映射"""
    url = f"{base_url}/emby/Library/SelectableMediaFolders?api_key={key}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return {folder['Id']: folder['Name'] for folder in data}
    return {}

async def check_updates(context: ContextTypes.DEFAULT_TYPE):
    """周期性扫描任务"""
    app = context.application
    
    base_url = os.getenv("REAL_URL")
    api_key = os.getenv("REAL_KEY")
    if not base_url or not api_key: return

    # 初始化
    if "watchtower_last_time" not in app.bot_data:
        async with aiohttp.ClientSession() as session:
            url = f"{base_url}/emby/Items?Recursive=true&SortBy=DateCreated&SortOrder=Descending&Limit=1&api_key={api_key}"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("Items"):
                        app.bot_data["watchtower_last_ids"] = [item['Id'] for item in data['Items']]
                    else:
                        app.bot_data["watchtower_last_ids"] = []
        return

    try:
        # 1. 获取最新条目
        async with aiohttp.ClientSession() as session:
            lib_map = await get_library_map(base_url, api_key)
            
            url = f"{base_url}/emby/Items?Recursive=true&SortBy=DateCreated&SortOrder=Descending&Limit=5&Fields=ParentId,Overview,ProductionYear,ProviderIds&api_key={api_key}"
            async with session.get(url) as resp:
                if resp.status != 200: return
                data = await resp.json()
                items = data.get("Items", [])

        if not items: return

        # 2. 筛选新条目
        old_ids = app.bot_data.get("watchtower_last_ids", [])
        new_items = []
        
        for item in items:
            if item['Id'] in old_ids: break
            new_items.append(item)
        
        app.bot_data["watchtower_last_ids"] = [i['Id'] for i in items]
        if not new_items: return

        # 3. 过滤白名单并推送
        for item in reversed(new_items):
            # 获取 LibraryName (尝试直接从 ParentId 映射，或者忽略复杂层级直接看类型)
            # 为了确保白名单生效，我们需要知道这个 item 属于哪个库
            # 简单策略：如果 item['Type'] 是 Movie，且我们在 WHITELIST 里有 "电影" 或 "remux电影"
            # 我们需要额外查一下它的 LibraryName，确保精准
            
            match_library = False
            async with aiohttp.ClientSession() as session:
                # 查询详情获取 LibraryName
                d_url = f"{base_url}/emby/Items/{item['Id']}?Fields=LibraryName&api_key={api_key}"
                async with session.get(d_url) as d_resp:
                    if d_resp.status == 200:
                        detail = await d_resp.json()
                        lib_name = detail.get("LibraryName")
                        if lib_name and lib_name in WHITELIST:
                            match_library = True
            
            if not match_library:
                continue

            # 发送通知 (可爱风文案)
            name = item.get('Name', '未知影片')
            year = item.get('ProductionYear', '')
            overview = item.get('Overview', '暂无简介...')
            if len(overview) > 100: overview = overview[:100] + "..."
            
            msg = (
                f"🔔 <b>叮咚！新片投递啦~</b>\n\n"
                f"🎬 <b>{name}</b> ({year})\n"
                f"🏷️ 媒体库: #{lib_name}\n"
                f"📝 简介: {overview}\n\n"
                f"<i>主人快准备好爆米花，看起来呀！🍿</i>"
            )

            img_url = f"{base_url}/emby/Items/{item['Id']}/Images/Primary?maxHeight=800&maxWidth=600&quality=90"
            try:
                await context.bot.send_photo(
                    chat_id=TARGET_CHAT_ID,
                    photo=img_url,
                    caption=msg,
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"推送失败: {e}")

    except Exception as e:
        print(f"Watchtower Error: {e}")

def register(app, ctx):
    if app.job_queue:
        app.job_queue.run_repeating(check_updates, interval=CHECK_INTERVAL, first=10)
        print("🎀 小甜心哨兵已上线，开始帮主人盯着媒体库啦...")
