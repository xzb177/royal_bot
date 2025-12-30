# -*- coding: utf-8 -*-
import re
import importlib
from pathlib import Path
from telegram.ext import CommandHandler

def _read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def _find_project_root() -> Path:
    # 当前文件：.../royal_bot/features/doctor.py
    return Path(__file__).resolve().parents[1]  # .../royal_bot

def _scan_features(project_root: Path):
    features_dir = project_root / "features"
    files = []
    if features_dir.exists():
        for f in sorted(features_dir.glob("*.py")):
            if f.name.startswith("_") or f.name in ("__init__.py",):
                continue
            files.append(f.stem)
    return files

def _parse_loaded_modules(project_root: Path):
    bot_py = project_root / "bot.py"
    text = _read_text(bot_py)
    # 抓取 bot.py 里出现的 royal_bot.features.xxx 字符串
    mods = set(re.findall(r'royal_bot\.features\.[a-zA-Z0-9_]+', text))
    return mods, bot_py

def _try_import(mod: str):
    try:
        importlib.import_module(mod)
        return None
    except Exception as e:
        return f"{type(e).__name__}: {e}"

def register(app, ctx):
    ui = ctx["ui"]
    cfg = ctx["cfg"]

    async def doctor(update, context):
        uid = update.effective_user.id
        if getattr(cfg, "OWNER_ID", None) and uid != int(cfg.OWNER_ID):
            await update.effective_message.reply_html(
                ui.panel("🩺 自检中心", ["这个命令只给老板用喔～"], "乖一点点 🎀")
            )
            return

        project_root = _find_project_root()
        features = _scan_features(project_root)
        loaded, bot_py = _parse_loaded_modules(project_root)

        exist_modules = {f"royal_bot.features.{name}" for name in features}

        # 1) 有文件但没加载
        not_loaded = sorted(exist_modules - loaded)

        # 2) bot.py 写了但文件不存在（或已删）
        dangling = sorted(m for m in loaded if m.startswith("royal_bot.features.") and m not in exist_modules)

        # 3) 逐个尝试导入检查报错
        import_errors = []
        for m in sorted(loaded):
            if not m.startswith("royal_bot.features."):
                continue
            err = _try_import(m)
            if err:
                import_errors.append((m, err))

        lines = [
            f"📂 features 插件文件：<b>{len(features)}</b> 个",
            f"🧩 bot.py 已加载模块：<b>{len([m for m in loaded if m.startswith('royal_bot.features.')])}</b> 个",
            f"🗂 bot.py 路径：<code>{bot_py}</code>",
            "",
        ]

        if not_loaded:
            lines.append("⚠️ <b>存在但没加载的插件</b>（建议加入 bot.py modules）：")
            lines += [f"• <code>{m}</code>" for m in not_loaded]
            lines.append("")

        if dangling:
            lines.append("🧨 <b>bot.py 里写了但文件不存在</b>（建议从 modules 移除）：")
            lines += [f"• <code>{m}</code>" for m in dangling]
            lines.append("")

        if import_errors:
            lines.append("❌ <b>导入失败的插件</b>（需要修复语法/依赖/路径）：")
            for m, err in import_errors[:20]:
                lines.append(f"• <code>{m}</code> — <i>{err}</i>")
            if len(import_errors) > 20:
                lines.append(f"… 还有 {len(import_errors)-20} 个错误未展开")
            lines.append("")

        if (not not_loaded) and (not dangling) and (not import_errors):
            lines.append("✅ 一切正常：插件齐全、加载一致、导入无报错 🎀")

        await update.effective_message.reply_html(
            ui.panel("🩺 一键自检报告", lines, "老板放心～我帮你把坑都照亮 😎")
        )

    app.add_handler(CommandHandler("doctor", doctor))
