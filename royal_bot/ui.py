# -*- coding: utf-8 -*-
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
title = "魔法世界"
BJ = "魔法世界"
class UI:
    @staticmethod
    def panel(text, lines=None):
        return f"✨ <b>{text}</b> ✨\n" + "━" * 15 + "\n" + ("\n".join(lines) if lines else "")
    @staticmethod
    def get_main_markup():
        return InlineKeyboardMarkup([[InlineKeyboardButton("🌸 开始祈愿", callback_data="start_pray")]])
ui = UI()
