"""🎬 Video: paginated list, detail, live refresh, delete."""
from __future__ import annotations

from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import fb_client
from db import TZ, parse_ts
from formatters import fmt_dt_local, fmt_int, fmt_num, fmt_vnd, fmt_watch, pct, short
from common import answer, esc, require_admin

PAGE_SIZE = 5


def _reel_url(v: dict) -> str | None:
    if v.get("fb_post_url"):
        return v["fb_post_url"]
    if v.get("fb_video_id"):
        return f"https://facebook.com/reel/{v['fb_video_id']}"
    return None


async def show_list(query, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> None:
    db = context.application.bot_data["db"]
    total = await db.count_videos()
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    vids = await db.list_videos(limit=PAGE_SIZE, offset=page * PAGE_SIZE)

    rows = []
    for v in vids:
        s = await db.latest_snapshot(v["id"]) or {}
        plays = int(s.get("plays") or 0)
        rows.append([InlineKeyboardButton(
            f"▶ {fmt_num(plays)} · {short(v['title'], 30)}",
            callback_data=f"v:d:{v['id']}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"v:l:{page - 1}"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"v:l:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("⬅️ Menu chính", callback_data="m:main")])

    await query.edit_message_text(
        f"🎬 <b>Video</b> — trang {page + 1}/{pages} (tổng {total})",
        reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML",
    )


async def _detail_text(db, cfg, vid: int) -> tuple[str, list]:
    v = await db.get_video(vid)
    if not v:
        return "⚠️ Không tìm thấy video.", []
    s = await db.latest_snapshot(v["id"]) or {}
    plays = int(s.get("plays") or 0)
    reach = int(s.get("reach") or 0)
    likes = int(s.get("likes") or 0)
    comments = int(s.get("comments") or 0)
    shares = int(s.get("shares") or 0)
    avg_ms = int(s.get("avg_watch_ms") or 0)
    length = int(s.get("length_sec") or 0)
    completion = pct(avg_ms, length * 1000) if length else "—"

    today = datetime.now(TZ).date().isoformat()
    srows = [r for r in await db.shopee_range("2000-01-01", today)
             if (r["product_name"] or "") == (v["product_name"] or "")]
    clicks = sum(int(r["clicks"] or 0) for r in srows)
    orders = sum(int(r["orders"] or 0) for r in srows)
    comm = sum(int(r["commission_vnd"] or 0) for r in srows)

    pub = fmt_dt_local(parse_ts(v.get("published_at")))
    lines = [
        f"🎬 <b>{esc(v['title'])}</b>",
        f"🛍️ {esc(v['product_name'])}"
        + (f" — {fmt_vnd(v['price_vnd'])}" if v.get("price_vnd") else ""),
        f"📅 Đăng: {pub}",
        "",
        f"👁 Lượt phát: <b>{fmt_int(plays)}</b>   👥 Reach: <b>{fmt_int(reach)}</b>",
        f"❤️ {fmt_int(likes)}   💬 {fmt_int(comments)}   🔁 {fmt_int(shares)}",
        f"⏱️ Xem TB: <b>{fmt_watch(avg_ms)}</b>   ✅ Xem hết ~{completion}",
        "",
        f"🖱 Click: <b>{fmt_int(clicks)}</b>   🛒 Đơn: <b>{fmt_int(orders)}</b>"
        f"   (CR {pct(orders, clicks)})",
        f"💰 Hoa hồng SP: <b>{fmt_vnd(comm)}</b>",
    ]
    kb = [
        [InlineKeyboardButton("🔄 Cập nhật số liệu", callback_data=f"v:live:{vid}")],
    ]
    url = _reel_url(v)
    if url:
        kb.append([InlineKeyboardButton("🔗 Mở reel", url=url)])
    kb.append([InlineKeyboardButton("🗑 Xóa video", callback_data=f"v:del:{vid}")])
    kb.append([InlineKeyboardButton("⬅️ Danh sách", callback_data="v:l:0")])
    return "\n".join(lines), kb


async def show_detail(query, context: ContextTypes.DEFAULT_TYPE, vid: int) -> None:
    db = context.application.bot_data["db"]
    cfg = context.application.bot_data["config"]
    text, kb = await _detail_text(db, cfg, vid)
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb),
                                  parse_mode="HTML", disable_web_page_preview=True)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await answer(query)
    if not await require_admin(update, context):
        return
    db = context.application.bot_data["db"]
    cfg = context.application.bot_data["config"]
    parts = query.data.split(":")
    action = parts[1]

    if action == "l":
        await show_list(query, context, page=int(parts[2]))
    elif action == "d":
        await show_detail(query, context, int(parts[2]))
    elif action == "live":
        vid = int(parts[2])
        v = await db.get_video(vid)
        await query.answer("⏳ Đang lấy số liệu mới…")
        m = await fb_client.fetch_reel_metrics(v.get("fb_video_id") if v else None,
                                              cfg.fb_page_token)
        if v and (m["ok"] or m["plays"] or m["likes"]):
            await db.add_snapshot(vid, plays=m["plays"], reach=m["reach"],
                                  avg_watch_ms=m["avg_watch_ms"], likes=m["likes"],
                                  comments=m["comments"], shares=m["shares"],
                                  length_sec=m["length_sec"])
            await show_detail(query, context, vid)
            await query.answer("✅ Đã cập nhật")
        else:
            err = "; ".join(m["errors"]) or "không rõ lỗi"
            await query.answer(f"⚠️ {err}", show_alert=True)
    elif action == "del":
        vid = int(parts[2])
        v = await db.get_video(vid)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 Xóa luôn", callback_data=f"v:delc:{vid}"),
             InlineKeyboardButton("Hủy", callback_data=f"v:d:{vid}")],
        ])
        await query.edit_message_text(
            f"Xóa video <b>{esc(v['title'] if v else '')}</b> khỏi hệ thống?\n"
            "(Xóa cả lịch sử số liệu đã lưu.)",
            reply_markup=kb, parse_mode="HTML")
    elif action == "delc":
        vid = int(parts[2])
        await db.delete_video(vid)
        await query.answer("🗑 Đã xóa")
        await show_list(query, context, page=0)
