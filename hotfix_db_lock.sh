#!/usr/bin/env bash
set -euo pipefail
cd /root/royal_bot

SERVICE=tgbot
ENV_FILE=/root/royal_bot/.env

# 读取 DB_FILE
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE" >/dev/null 2>&1 || true
fi
DB_FILE="${DB_FILE:-/root/royal_bot/royal_bot.db}"

ts=$(date +%Y%m%d-%H%M%S)
BKDIR="/root/royal_bot/_db_lockfix_$ts"
mkdir -p "$BKDIR"
cp -a royal_bot/features/binding.py "$BKDIR/" 2>/dev/null || true
cp -a "$DB_FILE" "$BKDIR/" 2>/dev/null || true
echo "[*] backup -> $BKDIR"

echo "[*] stop service"
systemctl stop "$SERVICE" || true

echo "[*] kill stray bot processes (if any)"
pkill -f "python3 .*royal_bot\.bot" 2>/dev/null || true
pkill -f "python3 -m royal_bot\.bot" 2>/dev/null || true
sleep 0.5

echo "[*] set WAL + busy_timeout on DB (safe)"
python3 - <<PY
import os, sqlite3
db = os.environ.get("DB_FILE","/root/royal_bot/royal_bot.db")
conn = sqlite3.connect(db, timeout=30)
cur = conn.cursor()
cur.execute("PRAGMA journal_mode=WAL;")
cur.execute("PRAGMA synchronous=NORMAL;")
cur.execute("PRAGMA busy_timeout=5000;")
conn.commit()
conn.close()
print("[OK] DB PRAGMA set: WAL + busy_timeout")
PY

echo "[*] patch binding.py to use timeout + retry"
python3 - <<'PY'
import re, time, pathlib

p = pathlib.Path("/root/royal_bot/royal_bot/features/binding.py")
s = p.read_text("utf-8", errors="ignore")

if "def _db_connect(" not in s:
    # 尽量放在 import sqlite3 之后
    m = re.search(r"^import\s+sqlite3\s*$", s, re.M)
    insert_pos = m.end() if m else 0
    helper = """

# --- HOTFIX: sqlite lock guard (WAL + busy_timeout + timeout + retry) ---
import time as _time

def _db_connect(db_path: str):
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
    except Exception:
        pass
    return conn

def _with_retry(fn, tries: int = 8, base_sleep: float = 0.12):
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last = e
            msg = str(e).lower()
            if "locked" in msg or "busy" in msg:
                _time.sleep(base_sleep * (i + 1))
                continue
            raise
    raise last
# --- END HOTFIX ---
"""
    s = s[:insert_pos] + helper + s[insert_pos:]

# 只针对最关键的 set_binding 写入点做替换（不大改你原逻辑）
# 1) 把 conn = sqlite3.connect(...) 替换成 conn = _db_connect(...)
s2 = re.sub(r"conn\s*=\s*sqlite3\.connect\(([^)]*)\)", r"conn = _db_connect(\1)", s)

# 2) 在 set_binding 里，把写入执行包进 _with_retry
#    寻找 `def set_binding` 块里第一次出现的 `cur.execute(`，把它改成 _with_retry(lambda: cur.execute(...))
def patch_set_binding(block: str) -> str:
    # 只包第一条 execute（通常是 INSERT/UPDATE）
    return re.sub(r"cur\.execute\((.+?)\)\s*$",
                  r"_with_retry(lambda: cur.execute(\1))",
                  block, count=1, flags=re.M)

m = re.search(r"(def\s+set_binding\s*\(.*?\):\n)([\s\S]*?)(\n(?:def\s+|\Z))", s2)
if m:
    head, body, tail = m.group(1), m.group(2), m.group(3)
    body2 = patch_set_binding(body)
    s2 = s2[:m.start()] + head + body2 + tail + s2[m.end():]

p.write_text(s2, "utf-8")
print("[OK] binding.py patched")
PY

echo "[*] syntax check"
python3 -m py_compile /root/royal_bot/royal_bot/features/binding.py

echo "[*] start service"
systemctl start "$SERVICE"
sleep 1
systemctl status "$SERVICE" --no-pager -l | sed -n '1,80p'

echo
echo "[DONE] lock 修复完成 ✅"
echo "现在去 TG 管理员那边再试一次：/approve 7（或最新的申请号）"
