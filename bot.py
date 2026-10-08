"""Entrypoint: FastAPI + python-telegram-bot (webhook) + APScheduler.

- WEBHOOK_URL có giá trị -> webhook mode (chạy trên Render free web service).
- WEBHOOK_URL để trống  -> polling mode (chạy local để test).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from telegram import Update

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("bot")

from api import create_api  # noqa: E402
from config import load_config  # noqa: E402
from db import DB, TZ  # noqa: E402
from bot_handlers import build_application  # noqa: E402
from jobs import setup_scheduler  # noqa: E402


async def main() -> None:
    cfg = load_config()

    db = DB(cfg.database_url)
    await db.connect()
    await db.init_schema()
    log.info("DB ready: %s", db.backend)

    ptb = build_application(cfg, db)
    ptb.bot_data["started_at"] = datetime.now(TZ)

    scheduler = setup_scheduler(ptb)
    scheduler.start()
    log.info("Scheduler started (snapshot 30m, daily/weekly 08:00 %s)", cfg.timezone)

    if cfg.webhook_url:
        import uvicorn

        fastapi_app = create_api(ptb, db, cfg)
        server = uvicorn.Server(uvicorn.Config(
            fastapi_app, host="0.0.0.0", port=cfg.port, log_level="info"))
        log.info("Webhook mode on port %d", cfg.port)
        await server.serve()
    else:
        await ptb.initialize()
        await ptb.start()
        await ptb.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        log.info("Polling mode — Ctrl+C để dừng")
        try:
            await asyncio.Event().wait()
        finally:
            await ptb.updater.stop()
            await ptb.stop()
            await ptb.shutdown()

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
