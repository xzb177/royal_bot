# -*- coding: utf-8 -*-
import sqlite3
import asyncio
from dataclasses import dataclass
from typing import Optional, List, Tuple

DDL = [
"""
CREATE TABLE IF NOT EXISTS users (
  tg_id INTEGER PRIMARY KEY,
  xp INTEGER NOT NULL DEFAULT 0,
  streak INTEGER NOT NULL DEFAULT 0,
  last_active TEXT DEFAULT '',
  last_msg_ts INTEGER NOT NULL DEFAULT 0,
  duel_wins INTEGER NOT NULL DEFAULT 0,
  duel_losses INTEGER NOT NULL DEFAULT 0,
  poster_pity_epic INTEGER NOT NULL DEFAULT 0,
  poster_pity_legendary INTEGER NOT NULL DEFAULT 0
);
""",
"""
CREATE TABLE IF NOT EXISTS bindings (
  tg_id INTEGER PRIMARY KEY,
  emby_id TEXT,
  emby_name TEXT
);
""",
"""
CREATE TABLE IF NOT EXISTS poster_collection (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tg_id INTEGER NOT NULL,
  item_id TEXT NOT NULL,
  title TEXT,
  year INTEGER,
  rating REAL,
  genres TEXT,
  image_url TEXT,
  tier TEXT,
  created_ts INTEGER NOT NULL
);
""",
"""
CREATE TABLE IF NOT EXISTS system_state (
  key TEXT PRIMARY KEY,
  value TEXT
);
""",
"""
CREATE TABLE IF NOT EXISTS daily_checkin (
  tg_id INTEGER PRIMARY KEY,
  last_day TEXT NOT NULL DEFAULT '',
  streak INTEGER NOT NULL DEFAULT 0
);
""",

"""
CREATE TABLE IF NOT EXISTS daily_stats (
  tg_id INTEGER NOT NULL,
  day TEXT NOT NULL,
  msgs INTEGER NOT NULL DEFAULT 0,
  spins INTEGER NOT NULL DEFAULT 0,
  posters_saved INTEGER NOT NULL DEFAULT 0,
  duels_won INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (tg_id, day)
);
""",

"""
CREATE TABLE IF NOT EXISTS daily_bounties (
  tg_id INTEGER NOT NULL,
  day TEXT NOT NULL,
  idx INTEGER NOT NULL,
  task_type TEXT NOT NULL,
  target INTEGER NOT NULL,
  reward_xp INTEGER NOT NULL,
  reward_item_id TEXT DEFAULT '',
  reward_item_name TEXT DEFAULT '',
  reward_item_qty INTEGER NOT NULL DEFAULT 0,
  claimed INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (tg_id, day, idx)
);
""",

"""
CREATE TABLE IF NOT EXISTS weekly_stats (
  tg_id INTEGER NOT NULL,
  week TEXT NOT NULL,
  msgs INTEGER NOT NULL DEFAULT 0,
  spins INTEGER NOT NULL DEFAULT 0,
  posters_saved INTEGER NOT NULL DEFAULT 0,
  duels_won INTEGER NOT NULL DEFAULT 0,
  bounties_claimed INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (tg_id, week)
);
""",

"""
CREATE TABLE IF NOT EXISTS weekly_spend (
  tg_id INTEGER NOT NULL,
  week TEXT NOT NULL,
  spent INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (tg_id, week)
);
""",

"""
CREATE TABLE IF NOT EXISTS user_cosmetics (
  tg_id INTEGER NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  updated_ts INTEGER NOT NULL,
  PRIMARY KEY (tg_id, key)
);
""",

"""
CREATE TABLE IF NOT EXISTS user_weapons (
  tg_id INTEGER NOT NULL,
  weapon_id TEXT NOT NULL,
  weapon_name TEXT NOT NULL,
  qty INTEGER NOT NULL DEFAULT 0,
  updated_ts INTEGER NOT NULL,
  PRIMARY KEY (tg_id, weapon_id)
);
""",
]

@dataclass
class DB:
    path: str

    def _conn(self):
        return sqlite3.connect(self.path, check_same_thread=False)

    async def init(self):
        def _():
            with self._conn() as c:
                for ddl in DDL:
                    c.execute(ddl)
                c.commit()
        await asyncio.to_thread(_)

    async def ensure_user(self, tg_id: int):
        def _():
            with self._conn() as c:
                c.execute("INSERT OR IGNORE INTO users(tg_id) VALUES (?)", (tg_id,))
                c.commit()
        await asyncio.to_thread(_)

    async def add_xp(self, tg_id: int, delta: int):
        await self.ensure_user(tg_id)
        def _():
            with self._conn() as c:
                c.execute("UPDATE users SET xp = xp + ? WHERE tg_id=?", (delta, tg_id))
                c.commit()
        await asyncio.to_thread(_)

    async def get_user(self, tg_id: int):
        await self.ensure_user(tg_id)
        def _():
            with self._conn() as c:
                return c.execute(
                    "SELECT xp, streak, last_active, last_msg_ts, duel_wins, duel_losses, poster_pity_epic, poster_pity_legendary "
                    "FROM users WHERE tg_id=?",
                    (tg_id,)
                ).fetchone()
        return await asyncio.to_thread(_)

    async def set_msg_ts(self, tg_id: int, ts: int):
        await self.ensure_user(tg_id)
        def _():
            with self._conn() as c:
                c.execute("UPDATE users SET last_msg_ts=? WHERE tg_id=?", (ts, tg_id))
                c.commit()
        await asyncio.to_thread(_)

    async def set_streak(self, tg_id: int, streak: int, day: str):
        await self.ensure_user(tg_id)
        def _():
            with self._conn() as c:
                c.execute("UPDATE users SET streak=?, last_active=? WHERE tg_id=?", (streak, day, tg_id))
                c.commit()
        await asyncio.to_thread(_)

    async def bind(self, tg_id: int, emby_id: str, emby_name: str):
        def _():
            with self._conn() as c:
                c.execute(
                    "INSERT OR REPLACE INTO bindings(tg_id, emby_id, emby_name) VALUES (?,?,?)",
                    (tg_id, emby_id, emby_name)
                )
                c.commit()
        await asyncio.to_thread(_)

    async def get_binding(self, tg_id: int) -> Optional[Tuple[str,str]]:
        def _():
            with self._conn() as c:
                return c.execute("SELECT emby_id, emby_name FROM bindings WHERE tg_id=?", (tg_id,)).fetchone()
        return await asyncio.to_thread(_)

    async def save_poster(self, tg_id: int, item_id: str, title: str, year: int, rating: float, genres: str, image_url: str, tier: str, ts: int):
        def _():
            with self._conn() as c:
                c.execute(
                    "INSERT INTO poster_collection(tg_id,item_id,title,year,rating,genres,image_url,tier,created_ts) VALUES (?,?,?,?,?,?,?,?,?)",
                    (tg_id, item_id, title, year, rating, genres, image_url, tier, ts)
                )
                c.commit()
        await asyncio.to_thread(_)

    async def list_posters(self, tg_id: int, limit: int = 8):
        def _():
            with self._conn() as c:
                return c.execute(
                    "SELECT item_id,title,year,rating,genres,image_url,tier,created_ts "
                    "FROM poster_collection WHERE tg_id=? ORDER BY created_ts DESC LIMIT ?",
                    (tg_id, limit)
                ).fetchall()
        return await asyncio.to_thread(_)

    async def list_posters_text(self, tg_id: int, limit: int = 30):
        def _():
            with self._conn() as c:
                return c.execute(
                    "SELECT title,year,tier,created_ts FROM poster_collection WHERE tg_id=? "
                    "ORDER BY created_ts DESC LIMIT ?",
                    (tg_id, limit)
                ).fetchall()
        return await asyncio.to_thread(_)

    async def get_state(self, key: str) -> Optional[str]:
        def _():
            with self._conn() as c:
                r = c.execute("SELECT value FROM system_state WHERE key=?", (key,)).fetchone()
                return r[0] if r else None
        return await asyncio.to_thread(_)

    async def set_state(self, key: str, value: str):
        def _():
            with self._conn() as c:
                c.execute("INSERT OR REPLACE INTO system_state(key,value) VALUES(?,?)", (key, value))
                c.commit()
        await asyncio.to_thread(_)

    async def bump_duel(self, winner: int, loser: int, stake: int):
        await self.ensure_user(winner)
        await self.ensure_user(loser)
        def _():
            with self._conn() as c:
                c.execute("UPDATE users SET duel_wins=duel_wins+1, xp=xp+? WHERE tg_id=?", (stake, winner))
                c.execute("UPDATE users SET duel_losses=duel_losses+1, xp=xp-? WHERE tg_id=?", (stake, loser))
                c.commit()
        await asyncio.to_thread(_)

    async def pity_inc(self, tg_id: int, epic_inc: int, leg_inc: int):
        await self.ensure_user(tg_id)
        def _():
            with self._conn() as c:
                c.execute(
                    "UPDATE users SET poster_pity_epic=poster_pity_epic+?, poster_pity_legendary=poster_pity_legendary+? WHERE tg_id=?",
                    (epic_inc, leg_inc, tg_id)
                )
                c.commit()
        await asyncio.to_thread(_)

    async def pity_reset_epic(self, tg_id: int):
        await self.ensure_user(tg_id)
        def _():
            with self._conn() as c:
                c.execute("UPDATE users SET poster_pity_epic=0 WHERE tg_id=?", (tg_id,))
                c.commit()
        await asyncio.to_thread(_)

    async def pity_reset_legendary(self, tg_id: int):
        await self.ensure_user(tg_id)
        def _():
            with self._conn() as c:
                c.execute("UPDATE users SET poster_pity_legendary=0 WHERE tg_id=?", (tg_id,))
                c.commit()
        await asyncio.to_thread(_)

    async def top_xp(self, limit: int = 10):
        def _():
            with self._conn() as c:
                return c.execute(
                    "SELECT tg_id, xp FROM users ORDER BY xp DESC LIMIT ?",
                    (limit,)
                ).fetchall()
        return await asyncio.to_thread(_)

    async def rank_xp(self, tg_id: int) -> int:
        await self.ensure_user(tg_id)
        def _():
            with self._conn() as c:
                xp = c.execute("SELECT xp FROM users WHERE tg_id=?", (tg_id,)).fetchone()[0]
                r = c.execute("SELECT COUNT(*) FROM users WHERE xp > ?", (xp,)).fetchone()[0]
                return int(r) + 1
        return await asyncio.to_thread(_)

    async def top_winrate(self, limit: int = 10, min_games: int = 3):
        def _():
            with self._conn() as c:
                rows = c.execute(
                    "SELECT tg_id, duel_wins, duel_losses FROM users "
                    "WHERE (duel_wins + duel_losses) >= ?",
                    (min_games,)
                ).fetchall()
                scored = []
                for uid, w, l in rows:
                    total = w + l
                    rate = (w / total) if total else 0.0
                    scored.append((uid, w, l, rate, total))
                scored.sort(key=lambda x: (x[3], x[4]), reverse=True)
                return scored[:limit]
        return await asyncio.to_thread(_)

    async def add_weapon(self, tg_id: int, weapon_id: str, weapon_name: str, qty: int, ts: int):
        await self.ensure_user(tg_id)
        def _():
            with self._conn() as c:
                c.execute(
                    "INSERT INTO user_weapons(tg_id, weapon_id, weapon_name, qty, updated_ts) VALUES(?,?,?,?,?) "
                    "ON CONFLICT(tg_id, weapon_id) DO UPDATE SET qty=qty+excluded.qty, updated_ts=excluded.updated_ts",
                    (tg_id, weapon_id, weapon_name, qty, ts)
                )
                c.commit()
        await asyncio.to_thread(_)

    async def list_weapons(self, tg_id: int):
        def _():
            with self._conn() as c:
                return c.execute(
                    "SELECT weapon_id, weapon_name, qty FROM user_weapons WHERE tg_id=? ORDER BY qty DESC",
                    (tg_id,)
                ).fetchall()
        return await asyncio.to_thread(_)



    async def poster_counts_by_tier(self, tg_id: int):
        """
        返回 dict: {"COMMON":x,"RARE":y,"EPIC":z,"LEGENDARY":k,"TOTAL":t}
        """
        await self.ensure_user(tg_id)
        def _():
            with self._conn() as c:
                rows = c.execute(
                    "SELECT tier, COUNT(*) FROM poster_collection WHERE tg_id=? GROUP BY tier",
                    (tg_id,)
                ).fetchall()
                d = {"COMMON":0,"RARE":0,"EPIC":0,"LEGENDARY":0}
                for tier, cnt in rows:
                    if tier in d:
                        d[tier] = int(cnt)
                d["TOTAL"] = sum(d.values())
                return d
        import asyncio
        return await asyncio.to_thread(_)

    async def top_weapon(self, tg_id: int):
        """
        返回 (weapon_id, weapon_name, qty) 或 None
        """
        await self.ensure_user(tg_id)
        def _():
            with self._conn() as c:
                r = c.execute(
                    "SELECT weapon_id, weapon_name, qty FROM user_weapons WHERE tg_id=? ORDER BY qty DESC, updated_ts DESC LIMIT 1",
                    (tg_id,)
                ).fetchone()
                return r
        import asyncio
        return await asyncio.to_thread(_)


    async def get_daily(self, tg_id: int):
        await self.ensure_user(tg_id)
        def _():
            with self._conn() as c:
                r = c.execute("SELECT last_day, streak FROM daily_checkin WHERE tg_id=?", (tg_id,)).fetchone()
                return r if r else ("", 0)
        import asyncio
        return await asyncio.to_thread(_)


    async def set_daily(self, tg_id: int, last_day: str, streak: int):
        await self.ensure_user(tg_id)
        def _():
            with self._conn() as c:
                c.execute(
                    "INSERT INTO daily_checkin(tg_id,last_day,streak) VALUES(?,?,?) "
                    "ON CONFLICT(tg_id) DO UPDATE SET last_day=excluded.last_day, streak=excluded.streak",
                    (tg_id, last_day, streak)
                )
                c.commit()
        import asyncio
        await asyncio.to_thread(_)


    async def get_weapon_qty(self, tg_id: int, weapon_id: str) -> int:
        await self.ensure_user(tg_id)
        def _():
            with self._conn() as c:
                r = c.execute(
                    "SELECT qty FROM user_weapons WHERE tg_id=? AND weapon_id=?",
                    (tg_id, weapon_id)
                ).fetchone()
                return int(r[0]) if r else 0
        import asyncio
        return await asyncio.to_thread(_)


    async def consume_weapon(self, tg_id: int, weapon_id: str, qty: int = 1) -> bool:
        """
        有则扣除 qty，返回 True；不足返回 False
        """
        await self.ensure_user(tg_id)
        qty = int(qty or 1)
        def _():
            with self._conn() as c:
                r = c.execute(
                    "SELECT qty FROM user_weapons WHERE tg_id=? AND weapon_id=?",
                    (tg_id, weapon_id)
                ).fetchone()
                cur = int(r[0]) if r else 0
                if cur < qty:
                    return False
                new = cur - qty
                if new <= 0:
                    c.execute("DELETE FROM user_weapons WHERE tg_id=? AND weapon_id=?", (tg_id, weapon_id))
                else:
                    c.execute("UPDATE user_weapons SET qty=? WHERE tg_id=? AND weapon_id=?", (new, tg_id, weapon_id))
                c.commit()
                return True
        import asyncio
        return await asyncio.to_thread(_)


    async def get_daily_stats(self, tg_id: int, day: str):
        await self.ensure_user(tg_id)
        def _():
            with self._conn() as c:
                r = c.execute(
                    "SELECT msgs, spins, posters_saved, duels_won FROM daily_stats WHERE tg_id=? AND day=?",
                    (tg_id, day)
                ).fetchone()
                return r if r else (0, 0, 0, 0)
        import asyncio
        return await asyncio.to_thread(_)


    async def inc_daily_stat(self, tg_id: int, day: str, field: str, delta: int = 1):
        await self.ensure_user(tg_id)
        if field not in ("msgs", "spins", "posters_saved", "duels_won"):
            return
        delta = int(delta or 1)
        def _():
            with self._conn() as c:
                c.execute("INSERT OR IGNORE INTO daily_stats(tg_id, day) VALUES(?,?)", (tg_id, day))
                c.execute(f"UPDATE daily_stats SET {field} = {field} + ? WHERE tg_id=? AND day=?", (delta, tg_id, day))
                c.commit()
        import asyncio
        await asyncio.to_thread(_)


    async def list_bounties(self, tg_id: int, day: str):
        await self.ensure_user(tg_id)
        def _():
            with self._conn() as c:
                return c.execute(
                    "SELECT idx, task_type, target, reward_xp, reward_item_id, reward_item_name, reward_item_qty, claimed "
                    "FROM daily_bounties WHERE tg_id=? AND day=? ORDER BY idx ASC",
                    (tg_id, day)
                ).fetchall()
        import asyncio
        return await asyncio.to_thread(_)


    async def upsert_bounty(self, tg_id: int, day: str, idx: int, task_type: str, target: int, reward_xp: int,
                           reward_item_id: str = "", reward_item_name: str = "", reward_item_qty: int = 0):
        await self.ensure_user(tg_id)
        def _():
            with self._conn() as c:
                c.execute(
                    "INSERT OR IGNORE INTO daily_bounties(tg_id, day, idx, task_type, target, reward_xp, reward_item_id, reward_item_name, reward_item_qty, claimed) "
                    "VALUES(?,?,?,?,?,?,?,?,?,0)",
                    (tg_id, day, idx, task_type, int(target), int(reward_xp), reward_item_id or "", reward_item_name or "", int(reward_item_qty or 0))
                )
                c.commit()
        import asyncio
        await asyncio.to_thread(_)


    async def claim_bounty(self, tg_id: int, day: str, idx: int):
        """
        标记领取，返回 bounty 行 or None
        """
        await self.ensure_user(tg_id)
        def _():
            with self._conn() as c:
                r = c.execute(
                    "SELECT idx, task_type, target, reward_xp, reward_item_id, reward_item_name, reward_item_qty, claimed "
                    "FROM daily_bounties WHERE tg_id=? AND day=? AND idx=?",
                    (tg_id, day, int(idx))
                ).fetchone()
                if not r:
                    return None
                if int(r[7]) == 1:
                    return r
                c.execute(
                    "UPDATE daily_bounties SET claimed=1 WHERE tg_id=? AND day=? AND idx=?",
                    (tg_id, day, int(idx))
                )
                c.commit()
                return r[:-1] + (1,)
        import asyncio
        return await asyncio.to_thread(_)


    async def inc_weekly_stat(self, tg_id: int, week: str, field: str, delta: int = 1):
        await self.ensure_user(tg_id)
        if field not in ("msgs", "spins", "posters_saved", "duels_won", "bounties_claimed"):
            return
        delta = int(delta or 1)
        def _():
            with self._conn() as c:
                c.execute("INSERT OR IGNORE INTO weekly_stats(tg_id, week) VALUES(?,?)", (tg_id, week))
                c.execute(f"UPDATE weekly_stats SET {field} = {field} + ? WHERE tg_id=? AND week=?", (delta, tg_id, week))
                c.commit()
        import asyncio
        await asyncio.to_thread(_)


    async def get_weekly_stats(self, tg_id: int, week: str):
        await self.ensure_user(tg_id)
        def _():
            with self._conn() as c:
                r = c.execute(
                    "SELECT msgs, spins, posters_saved, duels_won, bounties_claimed FROM weekly_stats WHERE tg_id=? AND week=?",
                    (tg_id, week)
                ).fetchone()
                return r if r else (0, 0, 0, 0, 0)
        import asyncio
        return await asyncio.to_thread(_)


    async def top_weekly(self, week: str, limit: int = 10):
        """
        points 规则（默认）：
        points = bounties*10 + duels*3 + posters*2 + spins*1 + (msgs/10)
        """
        def _():
            with self._conn() as c:
                rows = c.execute(
                    "SELECT tg_id, msgs, spins, posters_saved, duels_won, bounties_claimed, "
                    "(bounties_claimed*10 + duels_won*3 + posters_saved*2 + spins + CAST(msgs/10 AS INT)) AS points "
                    "FROM weekly_stats WHERE week=? "
                    "ORDER BY points DESC, bounties_claimed DESC, duels_won DESC LIMIT ?",
                    (week, int(limit))
                ).fetchall()
                return rows
        import asyncio
        return await asyncio.to_thread(_)


    async def get_weekly_spent(self, tg_id: int, week: str) -> int:
        await self.ensure_user(tg_id)
        def _():
            with self._conn() as c:
                r = c.execute("SELECT spent FROM weekly_spend WHERE tg_id=? AND week=?", (tg_id, week)).fetchone()
                return int(r[0]) if r else 0
        import asyncio
        return await asyncio.to_thread(_)


    async def add_weekly_spent(self, tg_id: int, week: str, delta: int):
        await self.ensure_user(tg_id)
        delta = int(delta or 0)
        def _():
            with self._conn() as c:
                c.execute("INSERT OR IGNORE INTO weekly_spend(tg_id, week, spent) VALUES(?,?,0)", (tg_id, week))
                c.execute("UPDATE weekly_spend SET spent = spent + ? WHERE tg_id=? AND week=?", (delta, tg_id, week))
                c.commit()
        import asyncio
        await asyncio.to_thread(_)


    async def get_cosmetic(self, tg_id: int, key: str):
        await self.ensure_user(tg_id)
        def _():
            with self._conn() as c:
                r = c.execute("SELECT value FROM user_cosmetics WHERE tg_id=? AND key=?", (tg_id, key)).fetchone()
                return r[0] if r else None
        import asyncio
        return await asyncio.to_thread(_)


    async def set_cosmetic(self, tg_id: int, key: str, value: str, ts: int):
        await self.ensure_user(tg_id)
        def _():
            with self._conn() as c:
                c.execute(
                    "INSERT INTO user_cosmetics(tg_id,key,value,updated_ts) VALUES(?,?,?,?) "
                    "ON CONFLICT(tg_id,key) DO UPDATE SET value=excluded.value, updated_ts=excluded.updated_ts",
                    (tg_id, key, value, int(ts))
                )
                c.commit()
        import asyncio
        await asyncio.to_thread(_)


    async def set_binding(self, tg_id: int, emby_id: str, emby_name: str):
        await self.ensure_user(tg_id)
        await self._ensure_bind_tables()
        def _():
            with self._conn() as c:
                c.execute(
                    "INSERT INTO bindings(tg_id, emby_id, emby_name) VALUES(?,?,?) "
                    "ON CONFLICT(tg_id) DO UPDATE SET emby_id=excluded.emby_id, emby_name=excluded.emby_name",
                    (tg_id, str(emby_id), str(emby_name))
                )
                c.commit()
        import asyncio
        await asyncio.to_thread(_)


    async def clear_binding(self, tg_id: int):
        await self.ensure_user(tg_id)
        await self._ensure_bind_tables()
        def _():
            with self._conn() as c:
                c.execute("DELETE FROM bindings WHERE tg_id=?", (tg_id,))
                c.commit()
        import asyncio
        await asyncio.to_thread(_)


    async def create_bind_request(self, tg_id: int, tg_name: str, emby_id: str, emby_name: str, ts: int):
        await self.ensure_user(tg_id)
        await self._ensure_bind_tables()
        def _():
            with self._conn() as c:
                # 如果已有 pending 的同 tg_id，就更新它
                r = c.execute("SELECT id FROM bind_requests WHERE tg_id=? AND status='pending' ORDER BY id DESC LIMIT 1", (tg_id,)).fetchone()
                if r:
                    rid = int(r[0])
                    c.execute(
                        "UPDATE bind_requests SET tg_name=?, emby_id=?, emby_name=?, ts=? WHERE id=?",
                        (tg_name or "", str(emby_id), str(emby_name), int(ts), rid)
                    )
                    c.commit()
                    return rid
                cur = c.execute(
                    "INSERT INTO bind_requests(tg_id, tg_name, emby_id, emby_name, ts, status) VALUES(?,?,?,?,?,'pending')",
                    (tg_id, tg_name or "", str(emby_id), str(emby_name), int(ts))
                )
                c.commit()
                return int(cur.lastrowid)
        import asyncio
        return await asyncio.to_thread(_)


    async def list_bind_requests(self, limit: int = 10):
        await self._ensure_bind_tables()
        limit = int(limit or 10)
        def _():
            with self._conn() as c:
                return c.execute(
                    "SELECT id, tg_id, tg_name, emby_id, emby_name, ts "
                    "FROM bind_requests WHERE status='pending' ORDER BY id DESC LIMIT ?",
                    (limit,)
                ).fetchall()
        import asyncio
        return await asyncio.to_thread(_)


    async def get_bind_request(self, rid: int):
        await self._ensure_bind_tables()
        def _():
            with self._conn() as c:
                r = c.execute(
                    "SELECT id, tg_id, tg_name, emby_id, emby_name, ts, status FROM bind_requests WHERE id=?",
                    (int(rid),)
                ).fetchone()
                return r
        import asyncio
        return await asyncio.to_thread(_)


    async def set_bind_request_status(self, rid: int, status: str):
        await self._ensure_bind_tables()
        def _():
            with self._conn() as c:
                c.execute("UPDATE bind_requests SET status=? WHERE id=?", (str(status), int(rid)))
                c.commit()
        import asyncio
        await asyncio.to_thread(_)

