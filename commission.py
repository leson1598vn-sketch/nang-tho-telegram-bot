"""💰 Hoa hồng: totals by range + daily table (ước tính)."""
from __future__ import annotations

from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from db import TZ, parse_day
from formatters import code_table, fmt_int, fmt_vnd, pct
from common import answer, esc, require_admin


def _kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗓 7 ngày", callback_data="c:7d"),
         InlineKeyboardButton("🗓 30 ngày", callback_data="c:30d")],
        [InlineKeyboardButton("⬅️ Menu chính", callback_data="m:main")],
    ])


async def show_menu(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    await query.edit_message_text(
        "💰 <b>Hoa hồng</b> — chọn khoảng thời gian:",
        reply_markup=_kb(), parse_mode="HTML")


async def build_text(context: ContextTypes.DEFAULT_TYPE, days: int) -> str:
    db = context.application.bot_data["db"]
    cfg = context.application.bot_data["config"]
    today = datetime.now(TZ).date()
    day_from = (today - timedelta(days=days - 1)).isoformat()
    rows = await db.shopee_range(day_from, today.isoformat())

    clicks = sum(int(r["clicks"] or 0) for r in rows)
    orders = sum(int(r["orders"] or 0) for r in rows)
    comm = sum(int(r["commission_vnd"] or 0) for r in rows)

    by_day: dict[str, list[int]] = {}
    for r in rows:
        d = parse_day(r["day"])
        b = by_day.setdefault(d, [0, 0, 0])
        b[0] += int(r["clicks"] or 0)
        b[1] += int(r["orders"] or 0)
        b[2] += int(r["commission_vnd"] or 0)

    lines = [
        f"💰 <b>Hoa hồng — {days} ngày qua</b>",
        f"🖱 Click: <b>{fmt_int(clicks)}</b>   🛒 Đơn: <b>{fmt_int(orders)}</b>"
        f"   (CR {pct(orders, clicks)})",
        f"💰 <b>Ước tính: {fmt_vnd(comm)}</b>",
    ]
    if by_day:
        table_rows = []
        for d in sorted(by_day)[-7:]:
            c, o, m = by_day[d]
            table_rows.append([d[5:], fmt_int(c), fmt_int(o), fmt_vnd(m)])
        lines += ["", "<b>Theo ngày (7 ngày gần nhất):</b>",
                  code_table(["Ngày", "Click", "Đơn", "Hoa hồng"], table_rows)]
    else:
        lines += ["", "<i>Chưa có số liệu affiliate trong khoảng này.</i>"]
    lines += ["", "💡 <i>Hoa hồng là số ước tính — Shopee duyệt & đối soát sau.</i>"]
    if not cfg.shopee_configured:
        lines += ["⚠️ <i>Chưa kết nối Shopee API — dùng /nhapdon để nhập tay.</i>"]
    return "\n".join(lines)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await answer(query)
    if not await require_admin(update, context):
        return
    days = 30 if query.data == "c:30d" else 7
    try:
        text = await build_text(context, days)
    except Exception as e:
        text = f"⚠️ Không lấy được số liệu: {esc(e)}"
    await query.edit_message_text(text, reply_markup=_kb(), parse_mode="HTML")
