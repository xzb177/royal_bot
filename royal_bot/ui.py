import html

# === 1. 定义 UI 类 (给 bot.py 用的) ===
class UI:
    def __init__(self):
        pass

    def kv(self, key, val):
        return f"<b>{key}</b>: {val}"

    def panel(self, title, lines, footer=""):
        content = "\n".join(lines)
        text = f"<b>{title}</b>\n\n{content}"
        if footer:
            text += f"\n\n<i>{footer}</i>"
        return text

# === 2. 定义模块级函数 (给 common.py 等插件用的) ===
def h1(text):
    return f"<b>=== {text} ===</b>"

def h2(text):
    return f"<b>--- {text} ---</b>"

def warn(text):
    return f"⚠️ {text}"

def ok(text):
    return f"✅ {text}"

def hint(text):
    return f"💡 {text}"

def mono(text):
    return f"<code>{text}</code>"

def esc(text):
    return html.escape(str(text))

def join(lines):
    return "\n".join(lines)

def soft_footer():
    return "<i>Powered by Royal Bot</i>"

def pre_block(lines):
    return "<pre>" + "\n".join(lines) + "</pre>"

def line_kv(k, v):
    return f"{k}: {v}"

# 这个是我们之前打的补丁，保留它
def section(title, body):
    return f"<b>{title}</b>\n{body}\n"

from datetime import timezone, timedelta
# 定义北京时间，修复 posters 插件的报错
BJ = timezone(timedelta(hours=8))
