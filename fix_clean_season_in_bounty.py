from pathlib import Path

p = Path("royal_bot/features/bounty.py")
s = p.read_text(encoding="utf-8")

lines = s.splitlines()
new_lines = [ln for ln in lines if 'CommandHandler("season"' not in ln]

if len(new_lines) != len(lines):
    p.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print("✅ 已移除 bounty.py 中所有 season 的 CommandHandler 行")
else:
    print("ℹ️ bounty.py 里本来就没有 season CommandHandler")
