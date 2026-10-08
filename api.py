"""HTTP layer: FastAPI app — Telegram webhook receiver + n8n integration endpoints.

Routes:
  GET  /health          -> liveness probe (Render health check + cron-job.org keep-alive)
  POST /webhook/{secret}-> Telegram updates (secret from WEBHOOK_SECRET)
  POST /api/pending     -> n8n (or anything) enqueues a video for approval (X-Webhook-Secret)
  POST /api/heartbeat   -> n8n pings after each run (X-Webhook-Secret)
"""
from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException, Request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update

from db import TZ

log = logging.getLogger("api")


def create_api(ptb_app, db, cfg) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await ptb_app.initialize()
        await ptb_app.start()
        if cfg.webhook_url and cfg.webhook_secret:
            url = f"{cfg.webhook_url}/webhook/{cfg.webhook_secret}"
            await ptb_app.bot.set_webhook(url=url, allowed_updates=Update.ALL_TYPES)
            log.info("Telegram webhook set")
        yield
        try:
            if cfg.webhook_url:
                await ptb_app.bot.delete_webhook()
        except Exception:
            pass
        await ptb_app.stop()
        await ptb_app.shutdown()

    app = FastAPI(title="Nang Tho Telegram Bot", lifespan=lifespan)

    @app.get("/health")
    async def health():
        try:
            await db.ping()
            db_ok = True
        except Exception:
            db_ok = False
        return {"ok": db_ok, "version": cfg.version,
                "backend": db.backend, "time": datetime.now(TZ).isoformat()}

    def _check(secret: str) -> None:
        if not cfg.n8n_webhook_secret or not hmac.compare_digest(
                secret or "", cfg.n8n_webhook_secret):
            raise HTTPException(status_code=401, detail="bad secret")

    @app.post("/api/pending")
    async def api_pending(request: Request,
                          x_webhook_secret: str = Header(default="")):
        _check(x_webhook_secret)
        data = await request.json()
        pid = await db.add_pending(
            title=str(data.get("title") or "(không tiêu đề)"),
            product_name=data.get("product_name"),
            preview_file_id=data.get("preview_file_id"),
            preview_url=data.get("preview_url"),
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Duyệt", callback_data=f"a:ok:{pid}"),
            InlineKeyboardButton("❌ Từ chối", callback_data=f"a:no:{pid}"),
        ]])
        for admin_id in cfg.admin_chat_ids:
            try:
                await ptb_app.bot.send_message(
                    admin_id,
                    f"🎬 <b>Video mới chờ duyệt</b> #{pid}\n"
                    f"🛍️ {data.get('product_name') or '—'}\n"
                    f"<i>Mở ✅ Duyệt video để xem preview.</i>",
                    parse_mode="HTML", reply_markup=kb)
            except Exception as e:
                log.warning("notify admin %s failed: %s", admin_id, e)
        return {"ok": True, "id": pid}

    @app.post("/api/heartbeat")
    async def api_heartbeat(x_webhook_secret: str = Header(default="")):
        _check(x_webhook_secret)
        await db.set_setting("n8n_last_seen", datetime.now(TZ).isoformat())
        return {"ok": True}

    @app.post("/webhook/{secret}")
    async def telegram_webhook(secret: str, request: Request):
        if not cfg.webhook_secret or not hmac.compare_digest(secret, cfg.webhook_secret):
            raise HTTPException(status_code=403, detail="forbidden")
        data = await request.json()
        update = Update.de_json(data, ptb_app.bot)
        await ptb_app.process_update(update)
        return {"ok": True}

    return app
