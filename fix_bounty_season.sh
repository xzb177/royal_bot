#!/usr/bin/env bash
set -e

cd /root/royal_bot
F="royal_bot/features/bounty.py"

echo "== 备份 bounty.py =="
cp "$F" "${F}.bak_season_$(date +%Y%m%d%H%M%S)"

python3 - << 'PY'
from pathlib import Path
import re

p = Path("/root/royal_bot/royal_bot/features/bounty.py")
s = p.read_text(encoding="utf-8")

# 找原来的 /bounty 命令注册行：app.add_handler(CommandHandler("bounty", xxx), group=YYY)
pat = re.compile(r'app\.add_handler\(CommandHandler\("bounty"\s*,\s*(\w+)\)\s*,\s*group=([^)]+)\)')
m = pat.search(s)
if not m:
    raise SystemExit("❌ 没找到 CommandHandler(\"bounty\", ...)，脚本不敢乱动")

func = m.group(1)
group = m.group(2)

inject = f'app.add_handler(CommandHandler("season", {func}), group={group})\\n'

if 'CommandHandler("season"' in s:
    print("ℹ️ 已经存在 season 的 CommandHandler，不需要再加了")
else:
    idx = s.find(m.group(0)) + len(m.group(0))
    s = s[:idx] + "\\n" + inject + s[idx:]
    p.write_text(s, encoding="utf-8")
    print("✅ 已为 /season 添加别名：使用函数", func, "，group=", group)
PY
