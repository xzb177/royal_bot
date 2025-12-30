# -*- coding: utf-8 -*-
"""
中文代理命令（全功能版）
让群友的中文聊天直接触发所有魔法效果
"""
import json
import os
import re
from telegram import Update
from telegram.ext import MessageHandler, CommandHandler, ContextTypes, filters

ALIAS_FILE = os.getenv("ZH_ALIAS_FILE", "/root/royal_bot/zh_alias.json")

# === 🔮 全插件中文映射表 ===
DEFAULT_ALIAS = {
    # --- 🏠 基础与菜单 ---
    "菜单": "menu",
    "魔法书": "menu",
    "呼叫管家": "menu",
    "功能": "menu",
    "帮助": "menu",

    # --- 👤 个人中心 (me) ---
    "我的": "me",
    "魔法档案": "me",
    "名片": "me",
    "资产": "me",
    "钱包": "me",
    "照镜子": "me",

    # --- 🔮 状态查询 (status) ---
    "水晶球": "status",
    "状态": "status",
    "服务器": "status",
    "探查": "status",
    "占卜": "status",

    # --- 📝 账号管理 (bind) ---
    "签订契约": "bindme",
    "绑定": "bindme",
    "认证": "bindme",
    "注册": "bindme",
    
    "解除契约": "unbind",
    "解绑": "unbind",
    "注销": "unbind",

    # --- 📅 签到系统 (daily) ---
    "每日祈福": "daily",
    "吸收魔力": "daily",
    "签到": "daily",
    "打卡": "daily",
    "日签": "daily",
    "领钱": "daily",

    # --- ✨ 抽卡系统 (poster) ---
    "命运祈愿": "poster",
    "抽海报": "poster",
    "抽卡": "poster",
    "观星": "poster",
    "祈愿": "poster",
    "盲盒": "poster",

    # --- 🎒 收藏系统 (wall) ---
    "收藏册": "wall",
    "魔法手账": "wall",
    "海报墙": "wall",
    "墙": "wall",
    "宝库": "wall",

    # --- 🛍️ 商店系统 (shop) ---
    "魔法杂货铺": "shop",
    "商店": "shop",
    "商城": "shop",
    "买称号": "shop",
    "消费": "shop",
    "氪金": "shop",

    # --- 🏦 银行借贷 (loan) ---
    "预支魔力": "loan",
    "魔法银行": "loan",
    "借钱": "loan",
    "贷款": "loan",
    "救济": "loan",
    "没钱了": "loan",

    # --- ⚔️ 战斗系统 (duel) ---
    "魔法切磋": "duel",
    "发起挑战": "duel",
    "决斗": "duel",
    "打架": "duel",
    "pk": "duel",
    "单挑": "duel",

    # --- 🧧 转账系统 (gift) ---
    "魔力转赠": "gift",
    "转账": "gift",
    "送钱": "gift",
    "发红包": "gift",
    "打赏": "gift",

    # --- 🎡 赌博系统 (spin) ---
    "命运转盘": "spin",
    "大转盘": "spin",
    "抽奖": "spin",
    "赌一赌": "spin",
    "梭哈": "spin",

    # --- 🏆 排行榜 (hall) ---
    "荣耀殿堂": "hall",
    "排行榜": "hall",
    "榜单": "hall",
    "富豪榜": "hall",
    "战神榜": "hall",

    # --- 🎋 求片系统 (request) ---
    "许愿池": "request",
    "求片": "request",
    "许愿": "request",
    "想看": "request",
    "点播": "request",
    "加片": "request",
}

def _load_alias():
    m = dict(DEFAULT_ALIAS)
    try:
        if os.path.exists(ALIAS_FILE):
            with open(ALIAS_FILE, "r", encoding="utf-8") as f:
                j = json.load(f)
            if isinstance(j, dict):
                for k, v in j.items():
                    if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip():
                        m[k.strip()] = v.strip().lstrip("/")
    except Exception:
        pass
    return m

def _handlers_dict(app):
    h = getattr(app, "handlers", None)
    if not h:
        h = getattr(app, "_handlers", None)
    return h if isinstance(h, dict) else {}

def _find_cmd_handler(app, cmd: str):
    cmd = cmd.lstrip("/").strip()
    for _, hs in _handlers_dict(app).items():
        for h in hs:
            if isinstance(h, CommandHandler):
                try:
                    if cmd in getattr(h, "commands", []):
                        return h
                except Exception:
                    pass
    return None

def _parse(text: str, alias_map: dict):
    t = (text or "").strip()
    if not t: return None
    if t.startswith("/"): return None

    # 优先匹配更长的词
    keys = sorted(alias_map.keys(), key=len, reverse=True)
    
    for k in keys:
        if t == k:
            return (alias_map[k], [])
        if t.startswith(k):
            rest = t[len(k):].strip()
            # 去掉分隔符：求片：哈利波特 -> 哈利波特
            rest = re.sub(r"^[：:，,]\s*", "", rest)
            if rest:
                args = [a for a in rest.split() if a]
            else:
                args = []
            return (alias_map[k], args)
    return None

async def _router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.effective_message or not update.effective_message.text: return
        text = update.effective_message.text.strip()
    except: return

    if not text or text.startswith('/'): return

    try:
        alias_map = context.application.bot_data.get("__zh_alias_map__")
        if not alias_map:
            alias_map = _load_alias()
            context.application.bot_data["__zh_alias_map__"] = alias_map

        parsed = _parse(text, alias_map)
        if not parsed: return

        cmd, args = parsed
        h = _find_cmd_handler(context.application, cmd)
        if not h: return

        # 注入参数
        try: context.args = args
        except: pass

        await h.callback(update, context)

        try:
            from telegram.ext import ApplicationHandlerStop
            raise ApplicationHandlerStop
        except: return
            
    except Exception as e:
        print(f"ZH_ALIAS Error: {e}")
        return

def register(app, ctx):
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _router), group=-999)
