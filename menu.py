"""/start, /help and the m:* main-menu router."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from . import approval, commission, overview, products, reports, system, videos
from .common import answer, esc, main_menu_kb, require_admin


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    await update.effective_message.reply_text(
        "👋 <b>Nàng Thơ Bot</b> — trợ lý số liệu Reels affiliate.\n"
        "Mở lúc nào cũng được, bấm nút là có số liệu mới nhất 👇",
        reply_markup=main_menu_kb(), parse_mode="HTML",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_admin(update, context):
        return
    await update.effective_message.reply_text(
        "<b>Lệnh nhanh</b>\n"
        "/start — mở menu chính\n"
        "/themvideo — đăng ký video mới (từng bước)\n"
        "/nhapdon — nhập số liệu Shopee tay\n"
        "/xoavideo — xóa video khỏi hệ thống\n"
        "/huy — hủy thao tác đang làm dở\n\n"
        "Còn lại cứ bấm nút, không cần nhớ lệnh.",
        parse_mode="HTML",
    )


async def on_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await answer(query)
    if not await require_admin(update, context):
        return
    action = query.data.split(":", 1)[1]
    if action == "ov":
        await overview.show_ranges(query, context)
    elif action == "v":
        await videos.show_list(query, context, page=0)
    elif action == "p":
        await products.show_list(query, context)
    elif action == "c":
        await commission.show_menu(query, context)
    elif action == "a":
        await approval.show_pending(query, context)
    elif action == "r":
        await reports.show_menu(query, context)
    elif action == "s":
        await system.show_status(query, context)
    elif action == "main":
        await query.edit_message_text(
            "🏠 <b>Menu chính</b>\nChọn mục muốn xem:",
            reply_markup=main_menu_kb(), parse_mode="HTML",
        )
