set -e
cd /root/royal_bot

SEASON_PY="/root/royal_bot/royal_bot/features/season.py"

echo "== 备份 season.py =="
cp "$SEASON_PY" "${SEASON_PY}.bak_$(date +%Y%m%d%H%M%S)"

python3 - <<'PY'
from pathlib import Path

p = Path("/root/royal_bot/royal_bot/features/season.py")
s = p.read_text(encoding="utf-8")

marker = "# --- HOTFIX: ensure /season registered ---"
if marker in s:
    print("hotfix 已存在，跳过注入")
else:
    s += """

# --- HOTFIX: ensure /season registered ---
from telegram.ext import CommandHandler as _CmdHandler

def register(app, cfg):
    \"\"\"强制注册 /season 命令的兜底函数。\"\"\"
    app.add_handler(_CmdHandler("season", season), group=-10)
# --- END HOTFIX ---
"""
    p.write_text(s, encoding="utf-8")
    print("已注入 hotfix 到 season.py")
PY

echo "== 语法检查 =="
python3 -m py_compile /root/royal_bot/royal_bot/features/season.py && echo "season.py ✅ compile OK"

echo "== 重启机器人 =="
systemctl restart tgbot
sleep 2
systemctl status tgbot --no-pager -l | sed -n '1,40p'
echo "== DONE =="
