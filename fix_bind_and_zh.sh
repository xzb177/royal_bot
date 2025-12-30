set -e
cd /root/royal_bot

echo "== 0) stop bot =="
systemctl stop tgbot 2>/dev/null || true

ts="$(date +%Y%m%d-%H%M%S)"
echo "== 1) backup to /root/royal_bot/_backup/$ts =="
mkdir -p "/root/royal_bot/_backup/$ts"
cp -a /root/royal_bot/royal_bot.db "/root/royal_bot/_backup/$ts/royal_bot.db" 2>/dev/null || true
cp -a /root/royal_bot/royal_bot "/root/royal_bot/_backup/$ts/royal_bot" 2>/dev/null || true
cp -a /root/royal_bot/.env "/root/royal_bot/_backup/$ts/.env" 2>/dev/null || true

echo "== 2) DB migrate (bindings.created_at + requests table/cols) =="
python3 - <<'PY'
import os, sqlite3, datetime

db = os.environ.get("DB_FILE", "/root/royal_bot/royal_bot.db")
conn = sqlite3.connect(db)
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = {r[0] for r in cur.fetchall()}

def cols(t):
    cur.execute(f"PRAGMA table_info({t})")
    return [r[1] for r in cur.fetchall()]

# bindings
if "bindings" not in tables:
    cur.execute("""CREATE TABLE bindings(
        tg_id INTEGER PRIMARY KEY,
        emby_name TEXT
    )""")
    tables.add("bindings")

bcols = cols("bindings")
if "created_at" not in bcols:
    cur.execute("ALTER TABLE bindings ADD COLUMN created_at TEXT")

# bind requests table (prefer existing if any)
req_table = None
candidates = ["bind_requests", "binding_requests", "bind_request", "binding_request"]
for t in candidates:
    if t in tables:
        req_table = t
        break
if req_table is None:
    req_table = "bind_requests"
    cur.execute("""CREATE TABLE bind_requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER NOT NULL,
        emby_name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT
    )""")
else:
    rcols = cols(req_table)
    if "status" not in rcols:
        cur.execute(f"ALTER TABLE {req_table} ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'")
    if "created_at" not in rcols:
        cur.execute(f"ALTER TABLE {req_table} ADD COLUMN created_at TEXT")

# store chosen req table name for binding2 module to read (optional)
# we won't write into env here; module will auto-detect too.

conn.commit()
conn.close()
print("DB OK:", db, "requests_table=", req_table)
PY

echo "== 3) write zh_alias.json (if missing) =="
if [ ! -f /root/royal_bot/zh_alias.json ]; then
cat >/root/royal_bot/zh_alias.json <<'JSON'
{
  "菜单": "/menu",
  "开始": "/start",
  "签到": "/daily",
  "绑定": "/bind",
  "我的": "/me",
  "墙": "/wall",
  "海报": "/poster",
  "周榜": "/bounty",
  "赛季": "/bounty",
  "审核": "/requests",
  "通过": "/approve",
  "同意": "/approve",
  "拒绝": "/reject",
  "驳回": "/reject"
}
JSON
fi

echo "== 4) overwrite zh_alias.py (priority group=-999, won't swallow /commands) =="
cat >/root/royal_bot/royal_bot/features/zh_alias.py <<'PY'
import os, json, re
from pathlib import Path
from telegram.ext import MessageHandler, filters

ALIAS_PATHS = [
    Path("/root/royal_bot/zh_alias.json"),
    Path(__file__).resolve().parent / "zh_alias.json"
]

def _load_alias():
    for p in ALIAS_PATHS:
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}

ALIASES = _load_alias()

def _rewrite(text: str) -> str | None:
    t = (text or "").strip()
    if not t:
        return None
    if t.startswith("/"):
        return None

    # exact match
    if t in ALIASES:
        return ALIASES[t]

    # token match: "绑定 yimaodidi" / "通过 7" / "拒绝7"
    m = re.match(r"^([^\s]+)\s*(.*)$", t)
    if not m:
        return None
    head, tail = m.group(1), (m.group(2) or "").strip()

    # handle "通过7" "拒绝7"
    if head not in ALIASES:
        m2 = re.match(r"^(通过|同意|拒绝|驳回)(\d+)$", head)
        if m2:
            head = m2.group(1)
            tail = m2.group(2)

    cmd = ALIASES.get(head)
    if not cmd:
        return None
    if tail:
        return f"{cmd} {tail}"
    return cmd

async def _router(update, context):
    msg = update.effective_message
    if not msg or not msg.text:
        return
    new_text = _rewrite(msg.text)
    if not new_text:
        return
    # modify in-place so later CommandHandlers can match it
    msg.text = new_text

def register(app, cfg):
    # group very early so rewrite happens before real command handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _router), group=-999)
PY

echo "== 5) create binding2.py (real inline buttons + callback + no crash) =="
cat >/root/royal_bot/royal_bot/features/binding2.py <<'PY'
import os, sqlite3, datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, CallbackQueryHandler
from telegram.ext import ApplicationHandlerStop

DB_FILE = os.environ.get("DB_FILE", "/root/royal_bot/royal_bot.db")
BIND_REQUIRES_APPROVAL = int(os.environ.get("BIND_REQUIRES_APPROVAL", "1") or "1")
OWNER_ID = int(os.environ.get("OWNER_ID", "0") or "0")
GROUP_ID = int(os.environ.get("GROUP_ID", "0") or "0")

def _conn():
    return sqlite3.connect(DB_FILE)

def _tables(cur):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {r[0] for r in cur.fetchall()}

def _cols(cur, t):
    cur.execute(f"PRAGMA table_info({t})")
    return [r[1] for r in cur.fetchall()]

def _detect_req_table(cur):
    tables = _tables(cur)
    for t in ("bind_requests", "binding_requests", "bind_request", "binding_request"):
        if t in tables:
            return t
    # create default
    cur.execute("""CREATE TABLE IF NOT EXISTS bind_requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER NOT NULL,
        emby_name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT
    )""")
    return "bind_requests"

def _ensure_schema():
    con = _conn()
    cur = con.cursor()
    tables = _tables(cur)

    if "bindings" not in tables:
        cur.execute("""CREATE TABLE bindings(
            tg_id INTEGER PRIMARY KEY,
            emby_name TEXT
        )""")
    bcols = _cols(cur, "bindings")
    if "created_at" not in bcols:
        try:
            cur.execute("ALTER TABLE bindings ADD COLUMN created_at TEXT")
        except Exception:
            pass

    req_table = _detect_req_table(cur)
    rcols = _cols(cur, req_table)
    if "status" not in rcols:
        try:
            cur.execute(f"ALTER TABLE {req_table} ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'")
        except Exception:
            pass
    if "created_at" not in rcols:
        try:
            cur.execute(f"ALTER TABLE {req_table} ADD COLUMN created_at TEXT")
        except Exception:
            pass

    con.commit()
    con.close()

def _upsert_binding(tg_id: int, emby_name: str):
    con = _conn()
    cur = con.cursor()
    _ensure_schema()
    cols = _cols(cur, "bindings")
    now = datetime.datetime.utcnow().isoformat(timespec="seconds")

    # build dynamic insert/update
    if "tg_id" in cols and "emby_name" in cols:
        if "created_at" in cols:
            cur.execute(
                "INSERT INTO bindings(tg_id, emby_name, created_at) VALUES(?,?,?) "
                "ON CONFLICT(tg_id) DO UPDATE SET emby_name=excluded.emby_name",
                (tg_id, emby_name, now)
            )
        else:
            cur.execute(
                "INSERT INTO bindings(tg_id, emby_name) VALUES(?,?) "
                "ON CONFLICT(tg_id) DO UPDATE SET emby_name=excluded.emby_name",
                (tg_id, emby_name)
            )
    con.commit()
    con.close()

def _create_request(tg_id: int, emby_name: str) -> int:
    con = _conn()
    cur = con.cursor()
    _ensure_schema()
    rt = _detect_req_table(cur)
    cols = _cols(cur, rt)
    now = datetime.datetime.utcnow().isoformat(timespec="seconds")

    if "created_at" in cols:
        cur.execute(f"INSERT INTO {rt}(tg_id, emby_name, status, created_at) VALUES(?,?,?,?)",
                    (tg_id, emby_name, "pending", now))
    else:
        cur.execute(f"INSERT INTO {rt}(tg_id, emby_name, status) VALUES(?,?,?)",
                    (tg_id, emby_name, "pending"))
    rid = cur.lastrowid
    con.commit()
    con.close()
    return rid

def _get_pending():
    con = _conn()
    cur = con.cursor()
    _ensure_schema()
    rt = _detect_req_table(cur)
    cols = _cols(cur, rt)

    # status field might not exist in some legacy, but we ensure it
    if "created_at" in cols:
        cur.execute(f"SELECT id, tg_id, emby_name, created_at FROM {rt} WHERE status='pending' ORDER BY id DESC")
        rows = cur.fetchall()
        con.close()
        return rows
    else:
        cur.execute(f"SELECT id, tg_id, emby_name FROM {rt} WHERE status='pending' ORDER BY id DESC")
        rows = cur.fetchall()
        con.close()
        return [(r[0], r[1], r[2], None) for r in rows]

def _set_request_status(rid: int, status: str):
    con = _conn()
    cur = con.cursor()
    _ensure_schema()
    rt = _detect_req_table(cur)
    cur.execute(f"UPDATE {rt} SET status=? WHERE id=?", (status, rid))
    con.commit()
    con.close()

def _kb(rid: int):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ 通过", callback_data=f"bind:approve:{rid}"),
        InlineKeyboardButton("❌ 拒绝", callback_data=f"bind:reject:{rid}")
    ]])

async def cmd_bind(update, context):
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user:
        return

    args = context.args or []
    if not args:
        await msg.reply_text("用法：/bind <Emby用户名>\n例如：/bind yimaodidi")
        raise ApplicationHandlerStop

    emby_name = args[0].strip()
    if not emby_name:
        await msg.reply_text("Emby 用户名不能为空。")
        raise ApplicationHandlerStop

    if BIND_REQUIRES_APPROVAL:
        rid = _create_request(user.id, emby_name)
        await msg.reply_text(f"📝 已提交绑定申请（#{rid}）\nEmby：{emby_name}\n⏳ 等管理员审核通过就生效~")

        # notify: same chat + optional owner/group
        text = (
            f"👑 Royal Bot | 绑定申请\n"
            f"• 申请号：#{rid}\n"
            f"• TG：{user.full_name} ({user.id})\n"
            f"• Emby：{emby_name}\n"
        )
        # send to current chat
        try:
            await context.bot.send_message(chat_id=msg.chat_id, text=text, reply_markup=_kb(rid))
        except Exception:
            pass
        # send to owner (only works if owner has started bot)
        if OWNER_ID:
            try:
                await context.bot.send_message(chat_id=OWNER_ID, text=text, reply_markup=_kb(rid))
            except Exception:
                pass
        # send to group if configured and not already in that group
        if GROUP_ID and GROUP_ID != msg.chat_id:
            try:
                await context.bot.send_message(chat_id=GROUP_ID, text=text, reply_markup=_kb(rid))
            except Exception:
                pass
    else:
        _upsert_binding(user.id, emby_name)
        await msg.reply_text(f"✅ 绑定成功：{emby_name}")

    raise ApplicationHandlerStop

async def cmd_requests(update, context):
    msg = update.effective_message
    rows = _get_pending()
    if not rows:
        await msg.reply_text("💤 当前没有待审核绑定申请。")
        raise ApplicationHandlerStop

    # send one card per request with real buttons
    for rid, tg_id, emby_name, created_at in rows[:20]:
        ts = f"\n• 时间：{created_at}" if created_at else ""
        text = f"💗 待审核绑定申请\n• 申请号：#{rid}\n• TG：{tg_id}\n• Emby：{emby_name}{ts}"
        await msg.reply_text(text, reply_markup=_kb(rid))
    raise ApplicationHandlerStop

async def _do_approve(update, context, rid: int):
    # find request info
    con = _conn()
    cur = con.cursor()
    _ensure_schema()
    rt = _detect_req_table(cur)
    cur.execute(f"SELECT tg_id, emby_name, status FROM {rt} WHERE id=?", (rid,))
    row = cur.fetchone()
    con.close()

    if not row:
        await update.effective_message.reply_text("找不到这个申请号～")
        return
    tg_id, emby_name, status = row
    if status != "pending":
        await update.effective_message.reply_text(f"这个申请已处理：{status}")
        return

    _set_request_status(rid, "approved")
    _upsert_binding(int(tg_id), str(emby_name))

    # notify
    await update.effective_message.reply_text(f"✅ 已通过申请 #{rid}，绑定生效：{emby_name}")
    try:
        await context.bot.send_message(chat_id=int(tg_id), text=f"✅ 你的绑定申请 #{rid} 已通过：{emby_name}")
    except Exception:
        pass

async def _do_reject(update, context, rid: int):
    con = _conn()
    cur = con.cursor()
    _ensure_schema()
    rt = _detect_req_table(cur)
    cur.execute(f"SELECT tg_id, emby_name, status FROM {rt} WHERE id=?", (rid,))
    row = cur.fetchone()
    con.close()

    if not row:
        await update.effective_message.reply_text("找不到这个申请号～")
        return
    tg_id, emby_name, status = row
    if status != "pending":
        await update.effective_message.reply_text(f"这个申请已处理：{status}")
        return

    _set_request_status(rid, "rejected")
    await update.effective_message.reply_text(f"❌ 已拒绝申请 #{rid}")
    try:
        await context.bot.send_message(chat_id=int(tg_id), text=f"❌ 你的绑定申请 #{rid} 已被拒绝：{emby_name}")
    except Exception:
        pass

async def cmd_approve(update, context):
    msg = update.effective_message
    if not context.args:
        await msg.reply_text("用法：/approve 申请号")
        raise ApplicationHandlerStop
    rid = int(str(context.args[0]).lstrip("#"))
    await _do_approve(update, context, rid)
    raise ApplicationHandlerStop

async def cmd_reject(update, context):
    msg = update.effective_message
    if not context.args:
        await msg.reply_text("用法：/reject 申请号")
        raise ApplicationHandlerStop
    rid = int(str(context.args[0]).lstrip("#"))
    await _do_reject(update, context, rid)
    raise ApplicationHandlerStop

async def cb_bind(update, context):
    q = update.callback_query
    if not q or not q.data:
        return
    await q.answer()
    try:
        _, action, rid_s = q.data.split(":", 2)
        rid = int(rid_s)
    except Exception:
        return

    if action == "approve":
        await _do_approve(update, context, rid)
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
    elif action == "reject":
        await _do_reject(update, context, rid)
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

def register(app, cfg):
    _ensure_schema()
    # Put our handlers very early so old/broken ones won't interfere
    app.add_handler(CommandHandler("bind", cmd_bind), group=-999)
    app.add_handler(CommandHandler("requests", cmd_requests), group=-999)
    app.add_handler(CommandHandler("approve", cmd_approve), group=-999)
    app.add_handler(CommandHandler("reject", cmd_reject), group=-999)
    app.add_handler(CallbackQueryHandler(cb_bind, pattern=r"^bind:(approve|reject):\d+$"), group=-999)
PY

echo "== 6) update .env FEATURE_MODULES: binding -> binding2, ensure zh_alias present =="
python3 - <<'PY'
from pathlib import Path
import re

envp = Path("/root/royal_bot/.env")
s = envp.read_text(encoding="utf-8") if envp.exists() else ""

def get_line(key):
    m = re.search(rf"^{re.escape(key)}=(.*)$", s, re.M)
    return m.group(1).strip() if m else None

fm = get_line("FEATURE_MODULES")
if not fm:
    fm = "royal_bot.features.status,royal_bot.features.common"

mods = [m.strip() for m in fm.split(",") if m.strip()]

# replace old binding
mods = ["royal_bot.features.binding2" if m == "royal_bot.features.binding" else m for m in mods]
if "royal_bot.features.binding2" not in mods:
    mods.append("royal_bot.features.binding2")

# ensure zh_alias exists
if "royal_bot.features.zh_alias" not in mods:
    mods.append("royal_bot.features.zh_alias")

new_fm = ",".join(mods)

if re.search(r"^FEATURE_MODULES=", s, re.M):
    s = re.sub(r"^FEATURE_MODULES=.*$", f"FEATURE_MODULES={new_fm}", s, flags=re.M)
else:
    if s and not s.endswith("\n"):
        s += "\n"
    s += f"FEATURE_MODULES={new_fm}\n"

envp.write_text(s, encoding="utf-8")
print("FEATURE_MODULES=", new_fm)
PY

echo "== 7) py_compile =="
python3 -m py_compile \
  /root/royal_bot/royal_bot/features/binding2.py \
  /root/royal_bot/royal_bot/features/zh_alias.py

echo "== 8) start bot =="
systemctl daemon-reload || true
systemctl start tgbot
sleep 1
systemctl status tgbot --no-pager -l | sed -n '1,140p'

echo "== DONE =="
echo "下一步测试："
echo "1) 群里/私聊发：菜单 / 签到 / 绑定 yimaodidi / 审核 / 通过 7（中文）"
echo "2) /requests 应该会发出【真按钮】✅通过 ❌拒绝"
echo "3) 点按钮后，/me 里应显示已绑定"
