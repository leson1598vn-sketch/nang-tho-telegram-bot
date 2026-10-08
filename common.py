"""Shared handler helpers: admin gate, escaping, keyboards."""
from __future__ import annotations

import html

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes


def esc(s) -> str:
    return html.escape(str(s or ""), quote=False)


def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    cfg = context.application.bot_data["config"]
    u = update.effective_user
    return bool(u) and u.id in cfg.admin_chat_ids


async def require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if is_admin(update, context):
        return True
    m = update.effective_message
    if m:
        await m.reply_text("⛔ Bot riêng tư — chỉ admin mới dùng được.")
    return False


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Tổng quan", callback_data="m:ov"),
         InlineKeyboardButton("🎬 Video", callback_data="m:v")],
        [InlineKeyboardButton("🛍️ Sản phẩm", callback_data="m:p"),
         InlineKeyboardButton("💰 Hoa hồng", callback_data="m:c")],
        [InlineKeyboardButton("✅ Duyệt video", callback_data="m:a"),
         InlineKeyboardButton("⏰ Báo cáo", callback_data="m:r")],
        [InlineKeyboardButton("⚙️ Hệ thống", callback_data="m:s")],
    ])


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Menu chính", callback_data="m:main")]])


def back_to(kb_extra: list | None = None, label: str = "⬅️ Menu chính",
            cb: str = "m:main") -> InlineKeyboardMarkup:
    rows = list(kb_extra or [])
    rows.append([InlineKeyboardButton(label, callback_data=cb)])
    return InlineKeyboardMarkup(rows)


async def answer(query) -> None:
    try:
        await query.answer()
    except Exception:
        pass
