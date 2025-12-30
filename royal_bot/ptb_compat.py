# -*- coding: utf-8 -*-
from telegram.ext import Defaults
from telegram.constants import ParseMode

def build_defaults():
    try:
        from telegram import LinkPreviewOptions
        return Defaults(
            parse_mode=ParseMode.HTML,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    except Exception:
        return Defaults(
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
