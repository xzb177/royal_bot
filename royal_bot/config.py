# -*- coding: utf-8 -*-
import os
from dataclasses import dataclass
from typing import List

def _csv(v: str) -> List[str]:
    return [x.strip() for x in (v or "").split(",") if x.strip()]

@dataclass(frozen=True)
class Config:
    BOT_TOKEN: str
    EMBY_URL: str
    EMBY_API_KEY: str
    DB_FILE: str
    OWNER_ID: int
    PUSH_GROUP_ID: int
    CHECK_INTERVAL: int
    EMBY_LIBRARY_WHITELIST: List[str]
    EMBY_VERIFY_SSL: bool

def load_config() -> Config:
    token = (os.getenv("BOT_TOKEN") or os.getenv("TOKEN") or "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN 未设置（请在 /root/royal_bot/.env 里配置）")

    return Config(
        BOT_TOKEN=token,
        EMBY_URL=(os.getenv("EMBY_URL") or "").rstrip("/"),
        EMBY_API_KEY=(os.getenv("EMBY_API_KEY") or os.getenv("API_KEY") or "").strip(),
        DB_FILE=(os.getenv("DB_FILE") or "/root/royal_bot/royal_bot.db").strip(),
        OWNER_ID=int(os.getenv("OWNER_ID") or "0"),
        PUSH_GROUP_ID=int(os.getenv("PUSH_GROUP_ID") or os.getenv("GROUP_ID") or "0"),
        CHECK_INTERVAL=int(os.getenv("CHECK_INTERVAL") or "300"),
        EMBY_LIBRARY_WHITELIST=_csv(os.getenv("EMBY_LIBRARY_WHITELIST") or ""),
        EMBY_VERIFY_SSL=(os.getenv("EMBY_VERIFY_SSL") or "0").strip() not in ("0","false","False","no","NO",""),
    )

# --- compat: provide CONFIG for old plugins ---
if 'CONFIG' not in globals():
    CONFIG = globals().get('cfg') or globals().get('Config') or globals()
# --- end compat ---

# --- compat: CONFIG export ---

# Some old plugins do: from royal_bot.config import CONFIG
# We export CONFIG in a very tolerant way.
from types import SimpleNamespace as _SimpleNamespace

def _build_CONFIG():
    g = globals()

    # 1) prefer cfg (dict or object)
    if "cfg" in g:
        c = g["cfg"]
        if isinstance(c, dict):
            return _SimpleNamespace(**c)
        return c

    # 2) prefer Config class / instance
    if "Config" in g:
        C = g["Config"]
        try:
            return C()  # instantiate
        except Exception:
            return C

    # 3) fallback: all UPPERCASE vars
    data = {k: v for k, v in g.items() if k.isupper()}
    return _SimpleNamespace(**data)

CONFIG = _build_CONFIG()

# --- end compat ---
