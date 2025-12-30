import os

# 这是加载器的位置
LOADER_PATH = "/root/royal_bot/royal_bot/loader.py"

if not os.path.exists(LOADER_PATH):
    print(f"❌ 找不到文件: {LOADER_PATH}")
    exit(1)

print(f"🔍 读取加载清单: {LOADER_PATH}")

with open(LOADER_PATH, "r", encoding="utf-8") as f:
    content = f.read()

# 我们要加的新插件
NEW_PLUGINS = ["bank", "request"]
added_count = 0

# 备份一下防止改坏
os.system(f"cp {LOADER_PATH} {LOADER_PATH}.bak")

# === 核心逻辑：找 shop，在它后面加 ===
# 尝试匹配带引号的 shop
for q in ['"', "'"]:
    target = f'{q}shop{q}'
    if target in content:
        print(f"✅ 找到了锚点: {target}")
        
        # 准备要插入的代码
        insertion = ""
        for p in NEW_PLUGINS:
            # 只有当里面没有这个插件时才加
            plugin_str = f'{q}{p}{q}'
            if plugin_str not in content:
                insertion += f', {plugin_str}'
                print(f"➕ 准备添加: {p}")
                added_count += 1
            else:
                print(f"👌 {p} 已经在清单里了")
        
        # 执行替换：把 "shop" 替换成 "shop", "bank", "request"
        if insertion:
            new_content = content.replace(target, target + insertion)
            with open(LOADER_PATH, "w", encoding="utf-8") as f:
                f.write(new_content)
            print("💾 修改已保存！")
        else:
            print("🍵 所有插件都已经存在，无需修改。")
        
        break
else:
    print("❌ 没在文件中找到 'shop' 这个词，脚本无法确定插入位置。")
    print("请把 /root/royal_bot/royal_bot/loader.py 的内容截图发给开发者。")

