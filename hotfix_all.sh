#!/usr/bin/env bash
set -euo pipefail
cd /root/royal_bot

SERVICE=tgbot
ENV_FILE=/root/royal_bot/.env

# 尽量从 .env 里读 DB_FILE
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE" >/dev/null 2>&1 || true
fi
DB_FILE="${DB_FILE:-/root/royal_bot/royal_bot.db}"

ts=$(date +%Y%m%d-%H%M%S)
BKDIR="/root/royal_bot/_hotfix_$ts"
mkdir -p "$BKDIR"
echo "[*] backup -> $BKDIR"
cp -a royal_bot "$BKDIR/" 2>/dev/null || true
cp -a "$ENV_FILE" "$BKDIR/" 2>/dev/null || true
cp -a "$DB_FILE" "$BKDIR/" 2>/dev/null || true

echo "[*] stop service"
systemctl stop "$SERVICE" || true

pyok(){ python3 -m py_compile "$1" >/dev/null 2>&1; }

restore_if_bad(){
  local f="$1"
  if [ ! -f "$f" ]; then
    echo "[SKIP] missing $f"
    return 0
  fi
  if pyok "$f"; then
    echo "[OK] $f syntax ok"
    return 0
  fi
  echo "[WARN] $f syntax broken, try restore from backups..."
  local best=""
  for cand in $(ls -1t "${f}".bak* 2>/dev/null || true); do
    if pyok "$cand"; then best="$cand"; break; fi
  done
  if [ -z "$best" ]; then
    echo "[ERR] no compiling backup found for $f"
    return 1
  fi
  cp -a "$best" "$f"
  echo "[FIX] restored $f from $best"
}

# 1) 如果你之前手滑把文件缩进改坏了，这里会自动从可编译备份恢复
restore_if_bad royal_bot/features/binding.py
restore_if_bad royal_bot/features/admin.py || true
restore_if_bad royal_bot/features/zh_alias.py || true

# 2) 数据库补列：解决 approve/reject “没反应”的真凶（created_at 缺失）
echo "[*] DB migrate (created_at columns)"
python3 - <<PY
import os, sqlite3
db = os.environ.get("DB_FILE","/root/royal_bot/royal_bot.db")
conn = sqlite3.connect(db)
cur = conn.cursor()

def ensure_col(table, col, ddl):
    cur.execute(f"PRAGMA table_info({table})")
    cols=[r[1] for r in cur.fetchall()]
    if col in cols:
        print(f"[OK] {table}.{col} exists")
        return
    print(f"[FIX] add {table}.{col}")
    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")

tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
for t in tables:
    tl = t.lower()
    if tl in ("bindings","binding","binds"):
        ensure_col(t, "created_at", "TEXT DEFAULT (datetime('now'))")
    if tl in ("bind_requests","binding_requests","requests","bindreq"):
        ensure_col(t, "created_at", "TEXT DEFAULT (datetime('now'))")

conn.commit()
conn.close()
print("[DONE] DB migration done")
PY

# 3) 新增：按钮回调模块（让“通过/拒绝”真的能点）
cat > royal_bot/features/bind_buttons.py <<'PY'
from __future__ import annotations
import re
from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

async def _call_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, cmd: str, args: list[str]) -> bool:
    app = context.application
    for group in sorted(app.handlers.keys()):
        for h in app.handlers[group]:
            if isinstance(h, CommandHandler) and cmd in getattr(h, "commands", []):
                try:
                    context.args = list(args)
                except Exception:
                    pass
                await h.callback(update, context)  # type: ignore[attr-defined]
                return True
    return False

async def _bind_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q:
        return
    await q.answer()
    m = re.match(r"^bind:(approve|reject):(\d+)$", q.data or "")
    if not m:
        return
    action, rid = m.group(1), m.group(2)
    ok = await _call_cmd(update, context, action, [rid])
    # 通过后尽量把按钮去掉，避免重复点
    if ok:
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

def register(app, cfg):
    app.add_handler(CallbackQueryHandler(_bind_cb, pattern=r"^bind:(approve|reject):\d+$"), group=50)
PY

# 4) 新增：中文代理模块（不吃掉 /命令！只匹配特定中文开头）
cat > royal_bot/features/zh_router.py <<'PY'
from __future__ import annotations
import re
from telegram import Update
from telegram.ext import MessageHandler, CommandHandler, ContextTypes, filters
from telegram.ext import ApplicationHandlerStop

ALIASES = {
    "菜单": ("menu", []),
    "帮助": ("menu", []),
    "我的": ("me", []),
    "个人": ("me", []),
    "签到": ("daily", []),
    "海报": ("poster", []),
    "墙": ("wall", []),
    "审核": ("requests", []),
    "周榜": ("bounty", []),
    "赛季": ("bounty", []),
}

PARAM_ALIASES = {
    "绑定": "bind",
    "同意": "approve",
    "通过": "approve",
    "拒绝": "reject",
}

async def _call_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, cmd: str, args: list[str]) -> bool:
    app = context.application
    for group in sorted(app.handlers.keys()):
        for h in app.handlers[group]:
            if isinstance(h, CommandHandler) and cmd in getattr(h, "commands", []):
                try:
                    context.args = list(args)
                except Exception:
                    pass
                await h.callback(update, context)  # type: ignore[attr-defined]
                return True
    return False

_PATTERN = re.compile(r"^(菜单|帮助|我的|个人|签到|海报|墙|审核|周榜|赛季|绑定|同意|通过|拒绝)(\s+.*)?$")

async def _router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg or not msg.text:
        return
    text = msg.text.strip()
    m = _PATTERN.match(text)
    if not m:
        return

    head = m.group(1)
    tail = (m.group(2) or "").strip()

    if head in ALIASES:
        cmd, extra = ALIASES[head]
        ok = await _call_cmd(update, context, cmd, extra)
        if ok:
            raise ApplicationHandlerStop
        return

    if head in PARAM_ALIASES:
        cmd = PARAM_ALIASES[head]
        args = tail.split() if tail else []
        ok = await _call_cmd(update, context, cmd, args)
        if ok:
            raise ApplicationHandlerStop

def register(app, cfg):
    # 关键点：~filters.COMMAND，且放到靠后 group，绝不影响 /xxx 命令
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _router), group=90)
PY

# 5) 写入 FEATURE_MODULES：启用 bind_buttons + zh_router，并移除旧 zh_alias（避免再次吃命令）
echo "[*] enable new modules in FEATURE_MODULES"
python3 - <<'PY'
import pathlib
env = pathlib.Path("/root/royal_bot/.env")
s = env.read_text("utf-8", errors="ignore").splitlines()
out=[]
for line in s:
    if line.startswith("FEATURE_MODULES="):
        mods=line.split("=",1)[1].strip()
        parts=[p.strip() for p in mods.split(",") if p.strip()]
        parts=[p for p in parts if p not in ("royal_bot.features.zh_alias","royal_bot.features.bind_buttons","royal_bot.features.zh_router")]
        parts.append("royal_bot.features.bind_buttons")
        parts.append("royal_bot.features.zh_router")
        line="FEATURE_MODULES="+",".join(parts)
    out.append(line)
env.write_text("\n".join(out).rstrip()+"\n","utf-8")
print("[OK] FEATURE_MODULES updated")
PY

echo "[*] syntax check"
python3 -m py_compile royal_bot/bot.py royal_bot/features/bind_buttons.py royal_bot/features/zh_router.py

echo "[*] start service"
systemctl daemon-reload || true
systemctl start "$SERVICE"
sleep 1
systemctl status "$SERVICE" --no-pager -l | sed -n '1,80p'

echo
echo "[DONE] 热修复完成 ✅"
echo "测试："
echo "1) 私聊机器人发：菜单 / 我的 / 签到"
echo "2) 群里发：绑定 yimaodidi（或你自定义）"
echo "3) 管理员卡片：点击 ✅通过 / ❌拒绝（按钮回调需要卡片有 callback_data 才会生效，下一步我再帮你把卡片改成真按钮）"
echo "4) 再用 /me 看是否已绑定"
