"""✅ Duyệt video: pending queue with approve/reject buttons.

n8n (or anything) can enqueue via POST /api/pending. On decision the bot
updates pending_videos.status and optionally pings N8N_WEBHOOK_URL.
"""
from __future__ import annotations

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from db import parse_ts
from formatters import fmt_dt_local
from .common import answer, esc, require_admin


def _kb(pid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Duyệt", callback_data=f"a:ok:{pid}"),
        InlineKeyboardButton("❌ Từ chối", callback_data=f"a:no:{pid}"),
    ]])


async def _notify_n8n(cfg, payload: dict) -> None:
    if not cfg.n8n_webhook_url:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            await c.post(cfg.n8n_webhook_url, json=payload,
                         headers={"X-Webhook-Secret": cfg.n8n_webhook_secret or ""})
    except Exception:
        pass


async def show_pending(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = context.application.bot_data["db"]
    items = await db.list_pending()
    if not items:
        await query.edit_message_text(
            "✅ <b>Duyệt video</b>\nKhông có video nào đang chờ.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Menu chính", callback_data="m:main")]]),
            parse_mode="HTML")
        return
    await query.edit_message_text(
        f"✅ <b>Duyệt video</b> — {len(items)} video đang chờ, gửi từng video bên dưới 👇",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ Menu chính", callback_data="m:main")]]),
        parse_mode="HTML")
    chat_id = query.message.chat_id
    for it in items:
        caption = (f"🎬 <b>{esc(it['title'])}</b>\n"
                   f"🛍️ {esc(it['product_name'] or '—')}\n"
                   f"🕐 {fmt_dt_local(parse_ts(it['created_at']))}")
        try:
            if it.get("preview_file_id"):
                await context.bot.send_video(chat_id, it["preview_file_id"],
                                             caption=caption, parse_mode="HTML",
                                             reply_markup=_kb(it["id"]))
            elif it.get("preview_url"):
                await context.bot.send_video(chat_id, it["preview_url"],
                                             caption=caption, parse_mode="HTML",
                                             reply_markup=_kb(it["id"]))
            else:
                await context.bot.send_message(chat_id, caption + "\n<i>(không có preview)</i>",
                                               parse_mode="HTML", reply_markup=_kb(it["id"]))
        except Exception:
            pass


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await answer(query)
    if not await require_admin(update, context):
        return
    db = context.application.bot_data["db"]
    cfg = context.application.bot_data["config"]
    _, decision, pid_s = query.data.split(":")
    pid = int(pid_s)
    item = await db.get_pending(pid)
    if not item or item["status"] != "pending":
        await query.answer("Video này đã được xử lý rồi.")
        return
    status = "approved" if decision == "ok" else "rejected"
    await db.set_pending_status(pid, status)
    mark = "✅ Đã duyệt" if decision == "ok" else "❌ Đã từ chối"
    new_caption = f"{mark} — <b>{esc(item['title'])}</b>"
    try:
        if query.message.video:
            await query.edit_message_caption(caption=new_caption, parse_mode="HTML")
        else:
            await query.edit_message_text(new_caption, parse_mode="HTML")
    except Exception:
        pass
    await query.answer(mark)
    await _notify_n8n(cfg, {"pending_id": pid, "decision": status,
                            "title": item["title"],
                            "product_name": item["product_name"]})
