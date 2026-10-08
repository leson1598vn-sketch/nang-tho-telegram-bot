"""📊 Tổng quan: range buttons -> shared builder from jobs."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from jobs import build_overview_text
from common import answer, esc, require_admin

RANGES = {"today": ("Hôm nay", 1), "7d": ("7 ngày qua", 7), "30d": ("30 ngày qua", 30)}


def _range_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Hôm nay", callback_data="ov:today"),
         InlineKeyboardButton("🗓 7 ngày", callback_data="ov:7d"),
         InlineKeyboardButton("🗓 30 ngày", callback_data="ov:30d")],
        [InlineKeyboardButton("⬅️ Menu chính", callback_data="m:main")],
    ])


async def show_ranges(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    await query.edit_message_text(
        "📊 <b>Tổng quan</b> — chọn khoảng thời gian:",
        reply_markup=_range_kb(), parse_mode="HTML",
    )


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await answer(query)
    if not await require_admin(update, context):
        return
    rng = query.data.split(":", 1)[1]
    label, days = RANGES.get(rng, ("7 ngày qua", 7))
    db = context.application.bot_data["db"]
    cfg = context.application.bot_data["config"]
    try:
        text = await build_overview_text(db, cfg, days, label)
    except Exception as e:
        text = f"⚠️ Không lấy được số liệu: {esc(e)}"
    await query.edit_message_text(text, reply_markup=_range_kb(), parse_mode="HTML")
