"""🛍️ Sản phẩm: list + detail (clicks/orders/CR/commission + linked videos)."""
from __future__ import annotations

from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from db import TZ
from formatters import fmt_int, fmt_num, fmt_vnd, pct, short
from .common import answer, esc, require_admin

CB_MAX = 36  # keep callback_data under Telegram's 64-byte limit


def _cb_name(name: str) -> str:
    return name[:CB_MAX]


async def _resolve(db, prefix: str) -> str | None:
    for n in await db.product_names():
        if n == prefix or n.startswith(prefix):
            return n
    return None


async def show_list(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = context.application.bot_data["db"]
    names = await db.product_names()
    rows = [[InlineKeyboardButton(f"🛍️ {short(n, 32)}", callback_data=f"p:d:{_cb_name(n)}")]
            for n in names]
    rows.append([InlineKeyboardButton("⬅️ Menu chính", callback_data="m:main")])
    await query.edit_message_text(
        f"🛍️ <b>Sản phẩm</b> ({len(names)}) — bấm để xem chi tiết:",
        reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")


async def show_detail(query, context: ContextTypes.DEFAULT_TYPE, prefix: str) -> None:
    db = context.application.bot_data["db"]
    name = await _resolve(db, prefix)
    if not name:
        await query.edit_message_text("⚠️ Không tìm thấy sản phẩm.")
        return
    today = datetime.now(TZ).date().isoformat()
    rows = [r for r in await db.shopee_range("2000-01-01", today)
            if (r["product_name"] or "") == name]
    clicks = sum(int(r["clicks"] or 0) for r in rows)
    orders = sum(int(r["orders"] or 0) for r in rows)
    comm = sum(int(r["commission_vnd"] or 0) for r in rows)

    vids = [v for v in await db.list_videos(limit=1000, offset=0)
            if (v["product_name"] or "") == name]
    plays_total = 0
    for v in vids:
        s = await db.latest_snapshot(v["id"]) or {}
        plays_total += int(s.get("plays") or 0)

    lines = [
        f"🛍️ <b>{esc(name)}</b>",
        "",
        f"🖱 Click: <b>{fmt_int(clicks)}</b>",
        f"🛒 Đơn: <b>{fmt_int(orders)}</b>   (CR {pct(orders, clicks)})",
        f"💰 Hoa hồng ước tính: <b>{fmt_vnd(comm)}</b>",
        f"🎬 {len(vids)} video   👁 {fmt_num(plays_total)} lượt phát",
    ]
    kb = []
    for v in vids[:5]:
        kb.append([InlineKeyboardButton(f"▶ {short(v['title'], 32)}",
                                        callback_data=f"v:d:{v['id']}")])
    kb.append([InlineKeyboardButton("⬅️ Sản phẩm", callback_data="m:p")])
    await query.edit_message_text("\n".join(lines),
                                  reply_markup=InlineKeyboardMarkup(kb),
                                  parse_mode="HTML")


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await answer(query)
    if not await require_admin(update, context):
        return
    parts = query.data.split(":", 1)
    if parts[0] == "p" and parts[1].startswith("d:"):
        await show_detail(query, context, parts[1][2:])
    else:
        await show_list(query, context)
