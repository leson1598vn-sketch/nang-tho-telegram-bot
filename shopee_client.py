"""Shopee Affiliate API wrapper.

Graceful degradation: if no credentials are configured, fetch_report()
returns {"configured": False} and the UI shows "chưa kết nối Shopee API"
with a pointer to the manual /nhapdon command instead of crashing.
"""
from __future__ import annotations

import hashlib
import hmac
import time

import httpx


class ShopeeClient:
    def __init__(self, base_url: str = "", appid: str = "", secret: str = ""):
        self.base_url = (base_url or "").rstrip("/")
        self.appid = appid or ""
        self.secret = secret or ""

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.appid and self.secret)

    def _sign(self, params: dict) -> str:
        raw = "&".join(f"{k}={params[k]}" for k in sorted(params))
        return hmac.new(self.secret.encode("utf-8"), raw.encode("utf-8"),
                        hashlib.sha256).hexdigest()

    async def fetch_report(self, date_from: str, date_to: str,
                           timeout: float = 20.0) -> dict:
        """Return {"ok", "configured", "rows": [...]} or {"ok": False, "error"}.

        Each row: {"day", "product_name", "clicks", "orders", "commission_vnd"}.
        dates: "YYYY-MM-DD".
        """
        if not self.configured:
            return {
                "ok": False,
                "configured": False,
                "error": ("Chưa cấu hình Shopee API "
                          "(SHOPEE_API_BASE_URL / SHOPEE_APPID / SHOPEE_SECRET). "
                          "Dùng /nhapdon để nhập số liệu tay."),
            }
        try:
            params = {
                "appid": self.appid,
                "timestamp": int(time.time()),
                "date_from": date_from,
                "date_to": date_to,
            }
            params["sign"] = self._sign(params)
            async with httpx.AsyncClient(timeout=timeout) as c:
                r = await c.post(f"{self.base_url}/affiliate/report", json=params)
            if r.status_code != 200:
                return {"ok": False, "configured": True,
                        "error": f"HTTP {r.status_code}: {r.text[:200]}"}
            rows = []
            for item in r.json().get("data", []) or []:
                rows.append({
                    "day": str(item.get("date") or item.get("day") or ""),
                    "product_name": str(item.get("product_name") or item.get("item_name") or "?"),
                    "clicks": int(item.get("clicks") or 0),
                    "orders": int(item.get("orders") or item.get("conversions") or 0),
                    "commission_vnd": int(item.get("commission") or item.get("estimated_commission") or 0),
                })
            return {"ok": True, "configured": True, "rows": rows}
        except Exception as e:
            return {"ok": False, "configured": True, "error": str(e)}

    async def test_connection(self, timeout: float = 15.0) -> dict:
        if not self.configured:
            return {"ok": False, "error": "Chưa cấu hình credentials"}
        res = await self.fetch_report(date_from="2000-01-01", date_to="2000-01-02",
                                      timeout=timeout)
        # Any HTTP-level success (even empty rows) counts as reachable.
        if res.get("ok") or "HTTP" not in str(res.get("error", "")):
            return {"ok": res.get("ok", False), "error": res.get("error", "")}
        return {"ok": False, "error": res.get("error", "")}
