# -*- coding: utf-8 -*-
import httpx
from typing import Any, Dict, List, Optional

class Emby:
    def __init__(self, base: str, api_key: str, verify_ssl: bool = False, lib_whitelist: Optional[List[str]] = None):
        self.base = (base or "").rstrip("/")
        self.key = (api_key or "").strip()
        self.verify_ssl = verify_ssl
        self.lib_whitelist = lib_whitelist or []

    def _p(self) -> Dict[str, Any]:
        return {"api_key": self.key}

    async def random_item(self) -> Dict[str, Any]:
        url = f"{self.base}/Items"
        params = {
            **self._p(),
            "IncludeItemTypes": "Movie,Series",
            "Recursive": "true",
            "SortBy": "Random",
            "Limit": "1",
            "Fields": "Genres,CommunityRating,ProductionYear",
        }
        if self.lib_whitelist:
            params["ParentId"] = self.lib_whitelist[0]

        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=15) as cli:
            r = await cli.get(url, params=params)
            r.raise_for_status()
            items = (r.json() or {}).get("Items") or []
            return items[0] if items else {}

    async def item_detail(self, item_id: str) -> Dict[str, Any]:
        url = f"{self.base}/Items/{item_id}"
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=15) as cli:
            r = await cli.get(url, params=self._p())
            r.raise_for_status()
            return r.json()

    async def item_primary_image_url(self, item_id: str) -> str:
        # 只用于 send_photo，不展示链接
        return f"{self.base}/Items/{item_id}/Images/Primary?maxHeight=1100&quality=90&api_key={self.key}"

    async def latest_item(self) -> Optional[Dict[str, Any]]:
        url = f"{self.base}/Items"
        params = {
            **self._p(),
            "IncludeItemTypes": "Movie,Series",
            "Recursive": "true",
            "SortBy": "DateCreated",
            "SortOrder": "Descending",
            "Limit": "1",
            "Fields": "Genres,CommunityRating,ProductionYear",
        }
        if self.lib_whitelist:
            params["ParentId"] = self.lib_whitelist[0]

        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=15) as cli:
            r = await cli.get(url, params=params)
            if r.status_code != 200:
                return None
            items = (r.json() or {}).get("Items") or []
            return items[0] if items else None

    async def sessions(self) -> List[Dict[str, Any]]:
        url = f"{self.base}/Sessions"
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=15) as cli:
            r = await cli.get(url, params=self._p())
            return r.json() if r.status_code == 200 else []

    async def users(self) -> List[Dict[str, Any]]:
        url = f"{self.base}/Users"
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=20) as cli:
            r = await cli.get(url, params=self._p())
            return r.json() if r.status_code == 200 else []

    async def libraries(self) -> List[Dict[str, Any]]:
        url = f"{self.base}/Library/MediaFolders"
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=20) as cli:
            r = await cli.get(url, params=self._p())
            data = r.json() if r.status_code == 200 else {}
            return data.get("Items") or []

# --- compat: EmbyEngine ---

# Some old plugins do: from royal_bot.emby import EmbyEngine
# Provide a minimal EmbyEngine wrapper (async httpx).
import os as _os
import httpx as _httpx

class EmbyEngine:
    def __init__(self, base_url=None, api_key=None, timeout=20):
        self.base_url = (base_url or _os.getenv("EMBY_URL", "")).rstrip("/")
        self.api_key = api_key or _os.getenv("EMBY_API_KEY", "")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    async def get(self, path: str, params=None):
        params = dict(params or {})
        if self.api_key:
            params.setdefault("api_key", self.api_key)
        async with _httpx.AsyncClient(timeout=self.timeout) as cli:
            r = await cli.get(self._url(path), params=params)
            r.raise_for_status()
            return r.json()

    async def post(self, path: str, params=None, json=None):
        params = dict(params or {})
        if self.api_key:
            params.setdefault("api_key", self.api_key)
        async with _httpx.AsyncClient(timeout=self.timeout) as cli:
            r = await cli.post(self._url(path), params=params, json=json)
            r.raise_for_status()
            return r.json()

# --- end compat ---

