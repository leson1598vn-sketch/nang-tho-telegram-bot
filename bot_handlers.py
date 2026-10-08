"""Handler package: registers every command / callback with the PTB Application."""
from __future__ import annotations

import logging

from telegram.ext import Application, CallbackQueryHandler, CommandHandler

import admin_conversations, approval, commission, menu, overview, products, reports, system, videos
from common import esc

log = logging.getLogger("bot_handlers")


async def _on_error(update, context) -> None:
    """Báo lỗi handler về cho admin để dễ debug (thay vì nút bấm 'đứng im')."""
    log.exception("Handler error: %s", context.error)
    try:
        cfg = context.application.bot_data["config"]
        for admin_id in cfg.admin_chat_ids:
            await context.bot.send_message(
                admin_id,
                f"⚠️ Bot gặp lỗi khi xử lý: {esc(str(context.error))[:400]}")
    except Exception:
        pass


def build_application(cfg, db) -> Application:
    app = Application.builder().token(cfg.telegram_token)
    if cfg.webhook_url:
        app = app.updater(None)  # webhook mode: FastAPI receives updates
    application = app.build()

    application.bot_data["config"] = cfg
    application.bot_data["db"] = db

    application.add_handler(CommandHandler("start", menu.cmd_start))
    application.add_handler(CommandHandler("help", menu.cmd_help))
    application.add_handler(CommandHandler("huy", admin_conversations.cmd_huy))
    application.add_handler(admin_conversations.themvideo_conv())
    application.add_handler(admin_conversations.nhapdon_conv())
    application.add_handler(admin_conversations.xoavideo_conv())

    application.add_handler(CallbackQueryHandler(menu.on_menu, pattern=r"^m:"))
    application.add_handler(CallbackQueryHandler(overview.on_callback, pattern=r"^ov:"))
    application.add_handler(CallbackQueryHandler(videos.on_callback, pattern=r"^v:"))
    application.add_handler(CallbackQueryHandler(products.on_callback, pattern=r"^p:"))
    application.add_handler(CallbackQueryHandler(commission.on_callback, pattern=r"^c:"))
    application.add_handler(CallbackQueryHandler(approval.on_callback, pattern=r"^a:"))
    application.add_handler(CallbackQueryHandler(reports.on_callback, pattern=r"^r:"))
    application.add_error_handler(_on_error)
    return application
