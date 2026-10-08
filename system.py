"""⚙️ Hệ thống: uptime, DB, FB API, Shopee API, n8n heartbeat, version."""
from __future__ import annotations

from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import fb_client
from db import TZ, parse_ts
from shopee_client import ShopeeClient
from .common import answer, esc, require_admin


async def show_status(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = context.application.bot_data["db"]
    cfg = context.application.bot_data["config"]
    started = context.application.bot_data.get("started_at")
    uptime = "—"
    if started:
        delta = datetime.now(TZ) - started
        d, rem = divmod(int(delta.total_seconds()), 86400)
        h, rem = divmod(rem, 3600)
        m, _ = divmod(rem, 60)
        uptime = f"{d}d {h}h {m}m" if d else f"{h}h {m}m"

    try:
        await db.ping()
        db_line = f"🟢 {db.backend}"
    except Exception as e:
        db_line = f"🔴 lỗi: {esc(str(e)[:80])}"

    fb = await fb_client.test_fb_connection(cfg.fb_page_id, cfg.fb_page_token)
    fb_line = f"🟢 {esc(fb.get('name') or 'OK')}" if fb["ok"] else f"🔴 {esc(fb.get('error', '')[:80])}"

    sh = ShopeeClient(cfg.shopee_base_url, cfg.shopee_appid, cfg.shopee_secret)
    sh_line = "🟢 đã cấu hình" if sh.configured else "⚪ chưa cấu hình (dùng /nhapdon)"

    n8n_seen = await db.get_setting("n8n_last_seen", "")
    n8n_line = "⚪ chưa thấy" if not n8n_seen else f"🟢 {fmt_seen(n8n_seen)}"

    snaps = await db.snapshot_count()
    vids = await db.count_videos()

    text = (
        f"⚙️ <b>Hệ thống</b> <i>v{esc(cfg.version)}</i>\n\n"
        f"🤖 Bot uptime: <b>{uptime}</b>\n"
        f"🗄️ DB: {db_line} — {vids} video, {snaps} snapshot\n"
        f"📘 Facebook API: {fb_line}\n"
        f"🛍️ Shopee API: {sh_line}\n"
        f"🔗 n8n heartbeat: {n8n_line}\n"
    )
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ Menu chính", callback_data="m:main")]]),
        parse_mode="HTML")


def fmt_seen(iso: str) -> str:
    dt = parse_ts(iso)
    if not dt:
        return iso
    delta = datetime.now(TZ) - dt
    mins = int(delta.total_seconds() // 60)
    if mins < 1:
        return "vừa xong"
    if mins < 60:
        return f"{mins} phút trước"
    return dt.strftime("%d/%m %H:%M")


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # routed via m:s in menu; kept for symmetry
    query = update.callback_query
    await answer(query)
    if not await require_admin(update, context):
        return
    await show_status(query, context)
