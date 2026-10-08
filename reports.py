"""⏰ Báo cáo: toggle daily/weekly, send-now buttons."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from jobs import send_daily_report, send_weekly_report
from .common import answer, require_admin


async def _states(db) -> tuple[str, str]:
    daily = await db.get_setting("report_daily", "on")
    weekly = await db.get_setting("report_weekly", "on")
    return daily, weekly


def _kb(daily: str, weekly: str) -> InlineKeyboardMarkup:
    d = "🟢 Bật" if daily == "on" else "🔴 Tắt"
    w = "🟢 Bật" if weekly == "on" else "🔴 Tắt"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📅 Báo cáo ngày: {d}", callback_data="r:tg:daily")],
        [InlineKeyboardButton(f"📆 Báo cáo tuần: {w}", callback_data="r:tg:weekly")],
        [InlineKeyboardButton("📨 Gửi báo cáo ngày ngay", callback_data="r:now:daily"),
         InlineKeyboardButton("📨 Gửi báo cáo tuần ngay", callback_data="r:now:weekly")],
        [InlineKeyboardButton("⬅️ Menu chính", callback_data="m:main")],
    ])


async def show_menu(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = context.application.bot_data["db"]
    daily, weekly = await _states(db)
    await query.edit_message_text(
        "⏰ <b>Báo cáo tự động</b>\n"
        "📅 Báo cáo ngày: gửi lúc <b>08:00</b> mỗi ngày\n"
        "📆 Báo cáo tuần: gửi lúc <b>08:00 thứ Hai</b>",
        reply_markup=_kb(daily, weekly), parse_mode="HTML")


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await answer(query)
    if not await require_admin(update, context):
        return
    db = context.application.bot_data["db"]
    parts = query.data.split(":")
    if parts[1] == "tg":
        key = "report_daily" if parts[2] == "daily" else "report_weekly"
        cur = await db.get_setting(key, "on")
        await db.set_setting(key, "off" if cur == "on" else "on")
        await show_menu(query, context)
        await query.answer("Đã cập nhật")
    elif parts[1] == "now":
        await query.answer("⏳ Đang tạo báo cáo…")
        if parts[2] == "daily":
            await send_daily_report(context.application)
        else:
            await send_weekly_report(context.application)
        await query.answer("✅ Đã gửi")
