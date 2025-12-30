#!/usr/bin/env bash
set -euo pipefail

echo "== 1) stop service =="
systemctl stop tgbot || true

echo "== 2) detect EnvironmentFile (.env) =="
ENV_FILE="$(systemctl cat tgbot 2>/dev/null | awk -F= '/EnvironmentFile=/{print $2}' | tail -n1 | tr -d '"' | sed 's/^-//')"
if [[ -z "${ENV_FILE}" ]]; then
  ENV_FILE="/root/royal_bot/.env"
fi
echo "ENV_FILE=${ENV_FILE}"

mkdir -p /root/royal_bot/_backup
stamp="$(date +%Y%m%d-%H%M%S)"
if [[ -f "${ENV_FILE}" ]]; then
  cp -af "${ENV_FILE}" "/root/royal_bot/_backup/.env.${stamp}.bak"
else
  echo "# created by fix script at ${stamp}" >"${ENV_FILE}"
fi

echo "== 3) ensure FEATURE_MODULES contains binding/admin/zh_alias =="
# 读取当前 FEATURE_MODULES（如果没有就空）
cur="$(grep -E '^FEATURE_MODULES=' "${ENV_FILE}" 2>/dev/null | tail -n1 | cut -d= -f2- || true)"
cur="${cur//\"/}"
cur="${cur//\'/}"

# 你原来常用的模块（尽量不动你已有的，只做“补齐”）
need=(
  "royal_bot.features.common"
  "royal_bot.features.status"
  "royal_bot.features.chatxp"
  "royal_bot.features.duel"
  "royal_bot.features.push"
  "royal_bot.features.binding"
  "royal_bot.features.admin"
  "royal_bot.features.logs"
  "royal_bot.features.posters"
  "royal_bot.features.xp"
  "royal_bot.features.daily"
  "royal_bot.features.me"
  "royal_bot.features.wall"
  "royal_bot.features.poster"
  "royal_bot.features.pity"
  "royal_bot.features.weapons"
  "royal_bot.features.hall"
  "royal_bot.features.winrate"
  "royal_bot.features.myrank"
  "royal_bot.features.season"
  "royal_bot.features.shop"
  "royal_bot.features.spin"
  "royal_bot.features.bounty"
  "royal_bot.features.doctor"
  "royal_bot.features.zh_alias"
)

# cur -> list
IFS=',' read -r -a arr <<<"${cur}"
# 去空白
for i in "${!arr[@]}"; do
  arr[$i]="$(echo "${arr[$i]}" | xargs)"
done

# 如果 cur 为空，就直接用 need；否则补齐缺的
if [[ -z "${cur}" ]]; then
  arr=("${need[@]}")
else
  for m in "${need[@]}"; do
    found=0
    for e in "${arr[@]}"; do
      [[ "${e}" == "${m}" ]] && found=1 && break
    done
    [[ $found -eq 0 ]] && arr+=("${m}")
  done
fi

new="$(IFS=,; echo "${arr[*]}")"

# 写回 ENV_FILE（先删旧的 FEATURE_MODULES 再追加）
grep -vE '^FEATURE_MODULES=' "${ENV_FILE}" >"/tmp/.env.tmp.${stamp}" || true
echo "FEATURE_MODULES=${new}" >>"/tmp/.env.tmp.${stamp}"
cp -af "/tmp/.env.tmp.${stamp}" "${ENV_FILE}"

echo "FEATURE_MODULES now =>"
grep -E '^FEATURE_MODULES=' "${ENV_FILE}" || true

echo "== 4) ensure zh_alias module file exists (stable router) =="
cat >/root/royal_bot/royal_bot/features/zh_alias.py <<'PY'
import re
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop

# 中文代理：只在“整句就是指令/以指令开头”时触发，避免误伤聊天
_RULES = [
    # 菜单/帮助
    (re.compile(r'^\s*(菜单|帮助)\s*$', re.I), lambda m: "/menu"),
    # 审核列表
    (re.compile(r'^\s*(审核|待审核|绑定审核|申请列表)\s*$', re.I), lambda m: "/requests"),
    # 绑定：绑定 用户名
    (re.compile(r'^\s*(绑定)\s+(.+?)\s*$', re.I), lambda m: f"/bind {m.group(2).strip()}"),
    # 通过/同意：通过 7
    (re.compile(r'^\s*(通过|同意)\s+(\d+)\s*$', re.I), lambda m: f"/approve {m.group(2)}"),
    # 拒绝/驳回：拒绝 7
    (re.compile(r'^\s*(拒绝|驳回)\s+(\d+)\s*$', re.I), lambda m: f"/reject {m.group(2)}"),
    # 常用功能（按需再加）
    (re.compile(r'^\s*(签到|每日签到)\s*$', re.I), lambda m: "/daily"),
    (re.compile(r'^\s*(海报|海报盲盒)\s*$', re.I), lambda m: "/poster"),
    (re.compile(r'^\s*(我的|我|资料|面板)\s*$', re.I), lambda m: "/me"),
    (re.compile(r'^\s*(周榜|榜单|排行)\s*$', re.I), lambda m: "/bounty"),
]

async def _router(update, context):
    msg = getattr(update, "message", None)
    if not msg or not getattr(msg, "text", None):
        return
    text = msg.text.strip()

    # 已经是 / 命令就不碰
    if text.startswith("/"):
        return

    # 防止递归：我们会把 text 改成 /xxx 后再 process_update 一次
    if context.chat_data.get("_zh_alias_busy"):
        return

    for rx, build in _RULES:
        m = rx.match(text)
        if not m:
            continue
        mapped = build(m)

        # 标记进入代理，避免二次进入
        context.chat_data["_zh_alias_busy"] = True
        try:
            msg.text = mapped
            await context.application.process_update(update)
        finally:
            context.chat_data.pop("_zh_alias_busy", None)

        # 代理成功后停止后续 handler，避免重复回复
        raise ApplicationHandlerStop

def register(app, cfg):
    # group 越小越优先：用一个极小值确保先跑
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _router), group=-999)
PY

echo "== 5) migrate sqlite DB (fix approve no response) =="
# DB_FILE 优先从 env 拿；没有就用默认
DB_FILE="$(grep -E '^DB_FILE=' "${ENV_FILE}" 2>/dev/null | tail -n1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)"
if [[ -z "${DB_FILE}" ]]; then
  DB_FILE="/root/royal_bot/royal_bot.db"
fi
echo "DB_FILE=${DB_FILE}"

python3 - <<PY
import sqlite3, os
db = "${DB_FILE}"
if not os.path.exists(db):
    raise SystemExit(f"DB not found: {db}")

conn = sqlite3.connect(db)
cur = conn.cursor()

def ensure_col(table, col, typ):
    try:
        cols = [r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()]
    except Exception as e:
        print(f"skip {table}: {e}")
        return
    if col not in cols:
        print(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
    else:
        print(f"OK {table}.{col} exists")

# 你的报错明确是 bindings.created_at 缺失
ensure_col("bindings", "created_at", "TEXT")

# 保险：有些实现会在请求表也写 created_at
ensure_col("bind_requests", "created_at", "TEXT")

conn.commit()
conn.close()
print("DB migration OK")
PY

echo "== 6) quick syntax check =="
python3 -m py_compile /root/royal_bot/royal_bot/features/zh_alias.py
python3 -m py_compile /root/royal_bot/royal_bot/features/binding.py || true
python3 -m py_compile /root/royal_bot/royal_bot/features/admin.py || true

echo "== 7) restart =="
systemctl daemon-reload || true
systemctl restart tgbot
sleep 1

echo "== 8) show loaded modules (last 80 lines) =="
journalctl -u tgbot -n 80 --no-pager | tail -n 80
echo
echo "== 9) show '加载插件' lines (confirm binding/admin/zh_alias) =="
journalctl -u tgbot -n 200 --no-pager | grep -E "加载插件" | tail -n 60 || true

echo "== DONE =="
echo "现在去群里测试："
echo "1) 发：审核   (应该等价 /requests)"
echo "2) 发：通过 7 (应该等价 /approve 7)"
echo "3) 发：绑定 yimiaodidi (应该等价 /bind yimiaodidi)"
