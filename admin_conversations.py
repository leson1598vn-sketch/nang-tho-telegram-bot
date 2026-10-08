"""Guided admin commands: /themvideo, /nhapdon, /xoavideo, /huy.

Step-by-step conversations so the admin never has to memorize syntax.
"""
from __future__ import annotations

import re
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (CallbackQueryHandler, CommandHandler, ContextTypes,
                          ConversationHandler, MessageHandler, filters)

from db import TZ, parse_day
from formatters import fmt_vnd, short
from .common import answer, esc, require_admin

# states
(T_TITLE, T_PRODUCT, T_PRICE, T_FBID, T_LINK, T_CONFIRM,
 N_DATE, N_PRODUCT, N_CLICKS, N_ORDERS, N_COMM, N_CONFIRM,
 X_SELECT, X_CONFIRM) = range(14)


def _parse_money(s: str) -> int | None:
    s = (s or "").strip().lower().replace("₫", "").replace("d", "")
    s = s.replace(".", "").replace(",", "").replace(" ", "")
    mult = 1000 if s.endswith("k") else 1
    s = s.rstrip("k")
    try:
        return int(s) * mult
    except ValueError:
        return None


def _parse_int(s: str) -> int | None:
    try:
        return int(re.sub(r"[^\d]", "", s or ""))
    except ValueError:
        return None


def _extract_fb(s: str) -> tuple[str | None, str | None]:
    """Return (video_id, post_url)."""
    s = (s or "").strip()
    m = re.search(r"(\d{8,})", s)
    vid = m.group(1) if m else (s or None)
    url = s if s.startswith("http") and "facebook.com" in s else None
    return vid, url


def _parse_date(s: str) -> str | None:
    s = (s or "").strip().lower()
    if s in ("hôm nay", "hom nay", "hn", "today", ""):
        return datetime.now(TZ).date().isoformat()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    return None


CANCEL_KB_HINT = "\n<i>Gõ /huy để hủy, /boqua để bỏ qua bước này.</i>"


async def cmd_huy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return ConversationHandler.END
    context.user_data.clear()
    await update.effective_message.reply_text("Đã hủy thao tác. /start để mở menu.")
    return ConversationHandler.END


# ================= /themvideo =================
async def tv_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return ConversationHandler.END
    context.user_data.clear()
    context.user_data["_step"] = T_TITLE
    await update.effective_message.reply_text(
        "🎬 <b>Thêm video mới</b> (1/5)\nNhập <b>tiêu đề</b> video:" + CANCEL_KB_HINT,
        parse_mode="HTML")
    return T_TITLE


async def tv_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.effective_message.text.strip()
    context.user_data["_step"] = T_PRODUCT
    await update.effective_message.reply_text(
        "🛍️ (2/5) Nhập <b>tên sản phẩm</b> affiliate:", parse_mode="HTML")
    return T_PRODUCT


async def tv_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["product"] = update.effective_message.text.strip()
    context.user_data["_step"] = T_PRICE
    await update.effective_message.reply_text(
        "💰 (3/5) Nhập <b>giá</b> (VD: 250000 hoặc 250k):" + CANCEL_KB_HINT,
        parse_mode="HTML")
    return T_PRICE


async def tv_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    v = _parse_money(update.effective_message.text)
    if v is None:
        await update.effective_message.reply_text("⚠️ Giá chưa đúng. Nhập lại (VD: 250000):")
        return T_PRICE
    context.user_data["price"] = v
    context.user_data["_step"] = T_FBID
    await update.effective_message.reply_text(
        "🔗 (4/5) Nhập <b>Facebook video ID</b> hoặc link reel:" + CANCEL_KB_HINT,
        parse_mode="HTML")
    return T_FBID


async def tv_fbid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vid, url = _extract_fb(update.effective_message.text)
    context.user_data["fb_video_id"] = vid
    context.user_data["fb_post_url"] = url
    context.user_data["_step"] = T_LINK
    await update.effective_message.reply_text(
        "🛒 (5/5) Nhập <b>link affiliate Shopee</b>:" + CANCEL_KB_HINT,
        parse_mode="HTML")
    return T_LINK


async def tv_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["link"] = update.effective_message.text.strip()
    return await tv_confirm_show(update, context)


async def tv_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /boqua: only PRICE, FBID, LINK are optional. """
    step = context.user_data.get("_step")
    if step == T_PRICE:
        context.user_data["price"] = None
        context.user_data["_step"] = T_FBID
        await update.effective_message.reply_text(
            "🔗 (4/5) Nhập <b>Facebook video ID</b> hoặc link reel:" + CANCEL_KB_HINT,
            parse_mode="HTML")
        return T_FBID
    if step == T_FBID:
        context.user_data["fb_video_id"] = None
        context.user_data["fb_post_url"] = None
        context.user_data["_step"] = T_LINK
        await update.effective_message.reply_text(
            "🛒 (5/5) Nhập <b>link affiliate Shopee</b>:" + CANCEL_KB_HINT,
            parse_mode="HTML")
        return T_LINK
    if step == T_LINK:
        context.user_data["link"] = None
        return await tv_confirm_show(update, context)
    await update.effective_message.reply_text("⚠️ Bước này bắt buộc, không bỏ qua được.")
    return step if isinstance(step, int) else T_TITLE


async def tv_confirm_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = context.user_data
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Lưu", callback_data="t:save"),
        InlineKeyboardButton("❌ Hủy", callback_data="t:cancel"),
    ]])
    await update.effective_message.reply_text(
        "📝 <b>Xác nhận video mới:</b>\n"
        f"🎬 {esc(d.get('title'))}\n"
        f"🛍️ {esc(d.get('product'))}\n"
        f"💰 {fmt_vnd(d.get('price')) if d.get('price') else '—'}\n"
        f"🆔 FB: {esc(d.get('fb_video_id') or '—')}\n"
        f"🔗 {esc(short(d.get('link') or '—', 40))}",
        reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    return T_CONFIRM


async def tv_confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await answer(query)
    if query.data == "t:save":
        db = context.application.bot_data["db"]
        d = context.user_data
        vid = await db.add_video(
            title=d["title"], product_name=d["product"],
            price_vnd=d.get("price"), fb_video_id=d.get("fb_video_id"),
            fb_post_url=d.get("fb_post_url"), affiliate_link=d.get("link"))
        await query.edit_message_text(f"✅ Đã lưu video <b>#{vid}</b>.", parse_mode="HTML")
    else:
        await query.edit_message_text("Đã hủy.")
    context.user_data.clear()
    return ConversationHandler.END


def themvideo_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("themvideo", tv_start)],
        states={
            T_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, tv_title)],
            T_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, tv_product)],
            T_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, tv_price)],
            T_FBID: [MessageHandler(filters.TEXT & ~filters.COMMAND, tv_fbid)],
            T_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, tv_link)],
            T_CONFIRM: [CallbackQueryHandler(tv_confirm_cb, pattern=r"^t:")],
        },
        fallbacks=[CommandHandler("huy", cmd_huy),
                   CommandHandler("boqua", tv_skip)],
        per_chat=True,
    )


# ================= /nhapdon =================
async def nd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return ConversationHandler.END
    context.user_data.clear()
    await update.effective_message.reply_text(
        "🛒 <b>Nhập số liệu Shopee tay</b> (1/5)\nNgày nào? (VD: 09/10/2026 hoặc gõ <i>hôm nay</i>):",
        parse_mode="HTML")
    return N_DATE


async def nd_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = _parse_date(update.effective_message.text)
    if not d:
        await update.effective_message.reply_text("⚠️ Ngày chưa đúng. Nhập dạng DD/MM/YYYY:")
        return N_DATE
    context.user_data["day"] = d
    db = context.application.bot_data["db"]
    names = await db.product_names()
    hint = ("\n<i>Gợi ý: " + ", ".join(esc(n) for n in names[:6]) + "</i>") if names else ""
    await update.effective_message.reply_text(
        f"🛍️ (2/5) <b>Tên sản phẩm</b> (ngày {parse_day(d)}):{hint}", parse_mode="HTML")
    return N_PRODUCT


async def nd_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["product"] = update.effective_message.text.strip()
    await update.effective_message.reply_text("🖱️ (3/5) Số <b>click</b>:", parse_mode="HTML")
    return N_CLICKS


async def nd_clicks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    v = _parse_int(update.effective_message.text)
    if v is None:
        await update.effective_message.reply_text("⚠️ Nhập số (VD: 120):")
        return N_CLICKS
    context.user_data["clicks"] = v
    await update.effective_message.reply_text("🛒 (4/5) Số <b>đơn</b>:", parse_mode="HTML")
    return N_ORDERS


async def nd_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    v = _parse_int(update.effective_message.text)
    if v is None:
        await update.effective_message.reply_text("⚠️ Nhập số (VD: 5):")
        return N_ORDERS
    context.user_data["orders"] = v
    await update.effective_message.reply_text(
        "💰 (5/5) <b>Hoa hồng</b> VND (VD: 36000):", parse_mode="HTML")
    return N_COMM


async def nd_comm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    v = _parse_money(update.effective_message.text)
    if v is None:
        await update.effective_message.reply_text("⚠️ Nhập số tiền (VD: 36000):")
        return N_COMM
    context.user_data["comm"] = v
    d = context.user_data
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Lưu", callback_data="n:save"),
        InlineKeyboardButton("❌ Hủy", callback_data="n:cancel"),
    ]])
    await update.effective_message.reply_text(
        "📝 <b>Xác nhận:</b>\n"
        f"📅 {parse_day(d['day'])} — 🛍️ {esc(d['product'])}\n"
        f"🖱️ {d['clicks']} click · 🛒 {d['orders']} đơn · 💰 {fmt_vnd(d['comm'])}",
        reply_markup=kb, parse_mode="HTML")
    return N_CONFIRM


async def nd_confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await answer(query)
    if query.data == "n:save":
        db = context.application.bot_data["db"]
        d = context.user_data
        await db.upsert_shopee_daily(d["day"], d["product"], d["clicks"],
                                     d["orders"], d["comm"], source="manual")
        await query.edit_message_text("✅ Đã lưu số liệu.", parse_mode="HTML")
    else:
        await query.edit_message_text("Đã hủy.")
    context.user_data.clear()
    return ConversationHandler.END


def nhapdon_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("nhapdon", nd_start)],
        states={
            N_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, nd_date)],
            N_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, nd_product)],
            N_CLICKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, nd_clicks)],
            N_ORDERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, nd_orders)],
            N_COMM: [MessageHandler(filters.TEXT & ~filters.COMMAND, nd_comm)],
            N_CONFIRM: [CallbackQueryHandler(nd_confirm_cb, pattern=r"^n:")],
        },
        fallbacks=[CommandHandler("huy", cmd_huy)],
        per_chat=True,
    )


# ================= /xoavideo =================
async def xv_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return ConversationHandler.END
    db = context.application.bot_data["db"]
    vids = await db.list_videos(limit=10, offset=0)
    if not vids:
        await update.effective_message.reply_text("Chưa có video nào.")
        return ConversationHandler.END
    rows = [[InlineKeyboardButton(f"🗑 {short(v['title'], 32)}",
                                  callback_data=f"x:sel:{v['id']}")] for v in vids]
    rows.append([InlineKeyboardButton("Hủy", callback_data="x:cancel")])
    await update.effective_message.reply_text(
        "🗑 <b>Xóa video</b> — chọn video:",
        reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
    return X_SELECT


async def xv_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await answer(query)
    if query.data == "x:cancel":
        await query.edit_message_text("Đã hủy.")
        return ConversationHandler.END
    vid = int(query.data.split(":")[2])
    db = context.application.bot_data["db"]
    v = await db.get_video(vid)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🗑 Xóa luôn", callback_data=f"x:yes:{vid}"),
        InlineKeyboardButton("Giữ lại", callback_data="x:no"),
    ]])
    await query.edit_message_text(
        f"Xóa <b>{esc(v['title'] if v else '')}</b>?\n(Xóa cả lịch sử số liệu.)",
        reply_markup=kb, parse_mode="HTML")
    return X_CONFIRM


async def xv_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await answer(query)
    if query.data.startswith("x:yes:"):
        vid = int(query.data.split(":")[2])
        await context.application.bot_data["db"].delete_video(vid)
        await query.edit_message_text("🗑 Đã xóa video.")
    else:
        await query.edit_message_text("Đã hủy.")
    return ConversationHandler.END


def xoavideo_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("xoavideo", xv_start)],
        states={
            X_SELECT: [CallbackQueryHandler(xv_select, pattern=r"^x:")],
            X_CONFIRM: [CallbackQueryHandler(xv_confirm, pattern=r"^x:")],
        },
        fallbacks=[CommandHandler("huy", cmd_huy)],
        per_chat=True,
    )
