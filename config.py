"""Load & validate environment configuration. No secrets are hardcoded."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

VERSION = "1.0.0"
DEFAULT_TZ = "Asia/Ho_Chi_Minh"


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name, default) or "").strip()


@dataclass
class Config:
    telegram_token: str
    admin_chat_ids: list[int] = field(default_factory=list)
    webhook_url: str = ""
    webhook_secret: str = ""
    database_url: str = ""
    fb_page_id: str = ""
    fb_page_token: str = ""
    shopee_base_url: str = ""
    shopee_appid: str = ""
    shopee_secret: str = ""
    n8n_webhook_secret: str = ""
    n8n_webhook_url: str = ""
    port: int = 10000
    timezone: str = DEFAULT_TZ
    version: str = VERSION

    @property
    def fb_configured(self) -> bool:
        return bool(self.fb_page_token)

    @property
    def shopee_configured(self) -> bool:
        return bool(self.shopee_base_url and self.shopee_appid and self.shopee_secret)


def load_config() -> Config:
    token = _env("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Thiếu TELEGRAM_BOT_TOKEN. Tạo bot tại @BotFather rồi điền vào .env")

    admins: list[int] = []
    for part in _env("ADMIN_CHAT_ID").replace(",", " ").split():
        try:
            admins.append(int(part))
        except ValueError:
            pass
    if not admins:
        raise RuntimeError("Thiếu ADMIN_CHAT_ID. Lấy chat id của bạn tại @userinfobot rồi điền vào .env")

    try:
        port = int(_env("PORT", "10000"))
    except ValueError:
        port = 10000

    return Config(
        telegram_token=token,
        admin_chat_ids=admins,
        webhook_url=_env("WEBHOOK_URL").rstrip("/"),
        webhook_secret=_env("WEBHOOK_SECRET"),
        database_url=_env("DATABASE_URL"),
        fb_page_id=_env("FB_PAGE_ID"),
        fb_page_token=_env("FB_PAGE_TOKEN"),
        shopee_base_url=_env("SHOPEE_API_BASE_URL").rstrip("/"),
        shopee_appid=_env("SHOPEE_APPID"),
        shopee_secret=_env("SHOPEE_SECRET"),
        n8n_webhook_secret=_env("N8N_WEBHOOK_SECRET"),
        n8n_webhook_url=_env("N8N_WEBHOOK_URL"),
        port=port,
        timezone=_env("TZ", DEFAULT_TZ) or DEFAULT_TZ,
    )
