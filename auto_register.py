import os
import re

# 搜索目录
BASE_DIR = "/root/royal_bot/royal_bot"
# 我们要找的“参照物” (既然 shop 能加载，我们就找 shop 在哪)
ANCHOR = "shop"
# 我们要添加的新插件
NEW_PLUGINS = ["bank", "request"]

print("🔍 正在寻找插件名单...")

target_file = None
for root, dirs, files in os.walk(BASE_DIR):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                # 找一个特征：它是列表形式，且包含 "shop"
                # 比如 features = ["shop", "duel"...]
                if f'"{ANCHOR}"' in content or f"'{ANCHOR}'" in content:
                    # 再次确认看起来像是一个列表定义
                    if "[" in content and "]" in content:
                        print(f"✅ 找到了！名单在文件: {path}")
                        target_file = path
                        break
    if target_file: break

if not target_file:
    print("❌ 没找到插件名单配置文件，请联系作者手动修改！")
    exit(1)

# === 开始修改 ===
with open(target_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
added = False

for line in lines:
    # 如果这行包含 "shop" (参照物)，我们就在它下面加新插件
    if (f'"{ANCHOR}"' in line or f"'{ANCHOR}'" in line) and not added:
        new_lines.append(line)
        # 检查缩进
        indent = re.match(r"\s*", line).group()
        
        for p in NEW_PLUGINS:
            # 只有当文件里还没写这个插件时才加
            if f'"{p}"' not in content and f"'{p}'" not in content:
                print(f"➕ 正在添加插件: {p}")
                # 模仿上一行的格式，加个逗号
                new_lines.append(f'{indent}"{p}",\n')
            else:
                print(f"👌 插件 {p} 已经存在，跳过。")
        added = True
    else:
        new_lines.append(line)

# 写入回文件
with open(target_file, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("🎉 注册完成！")
