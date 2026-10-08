"""Facebook Graph API client for Reels metrics.

Every call is wrapped in try/except with a timeout: partial failures keep
partial data and the bot reports which source is down instead of crashing.
"""
from __future__ import annotations

import httpx

GRAPH_VERSION = "v21.0"
BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"

INSIGHT_METRICS = [
    "blue_reels_play_count",          # số lượt phát reel
    "post_impressions_unique",        # reach
    "post_video_avg_time_watched",    # ms xem trung bình
    "post_video_likes_by_reaction_type",
    "post_video_social_actions",      # comment + share (+ like)
    "post_video_view_time",
]


def _last_value(entry: dict):
    vals = (entry or {}).get("values") or []
    return vals[-1].get("value") if vals else None


def _as_int(v) -> int:
    try:
        if isinstance(v, dict):  # breakdown theo reaction -> cộng tổng
            return int(sum(int(x or 0) for x in v.values()))
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


async def fetch_reel_metrics(video_id: str, page_token: str, timeout: float = 20.0) -> dict:
    """Fetch metrics for one reel. Never raises; errors are collected in the dict."""
    out = {
        "ok": False, "video_id": video_id,
        "plays": 0, "reach": 0, "avg_watch_ms": 0,
        "likes": 0, "comments": 0, "shares": 0, "length_sec": 0,
        "errors": [],
    }
    if not page_token:
        out["errors"].append("Chưa cấu hình FB_PAGE_TOKEN")
        return out
    if not video_id:
        out["errors"].append("Video chưa có fb_video_id")
        return out

    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.get(
                f"{BASE}/{video_id}/video_insights",
                params={"metric": ",".join(INSIGHT_METRICS), "access_token": page_token},
            )
        if r.status_code == 200:
            for entry in r.json().get("data", []):
                name, val = entry.get("name"), _last_value(entry)
                if name == "blue_reels_play_count":
                    out["plays"] = _as_int(val)
                elif name == "post_impressions_unique":
                    out["reach"] = _as_int(val)
                elif name == "post_video_avg_time_watched":
                    out["avg_watch_ms"] = _as_int(val)
                elif name == "post_video_likes_by_reaction_type":
                    out["likes"] = _as_int(val)
                elif name == "post_video_social_actions" and isinstance(val, dict):
                    out["comments"] = _as_int(val.get("comment"))
                    out["shares"] = _as_int(val.get("share"))
        else:
            out["errors"].append(f"video_insights HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:  # network / timeout / parse
        out["errors"].append(f"video_insights lỗi: {e}")

    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.get(
                f"{BASE}/{video_id}",
                params={
                    "fields": "likes.summary(true),comments.summary(true),shares,length",
                    "access_token": page_token,
                },
            )
        if r.status_code == 200:
            d = r.json()
            out["likes"] = out["likes"] or _as_int((d.get("likes") or {}).get("summary", {}).get("total_count"))
            out["comments"] = out["comments"] or _as_int((d.get("comments") or {}).get("summary", {}).get("total_count"))
            out["shares"] = out["shares"] or _as_int((d.get("shares") or {}).get("count"))
            out["length_sec"] = _as_int(d.get("length"))
        else:
            out["errors"].append(f"video fields HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        out["errors"].append(f"video fields lỗi: {e}")

    out["ok"] = not out["errors"]
    return out


async def test_fb_connection(page_id: str, page_token: str, timeout: float = 15.0) -> dict:
    """Quick health check for the ⚙️ Hệ thống page."""
    if not page_token:
        return {"ok": False, "error": "Chưa cấu hình FB_PAGE_TOKEN"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.get(f"{BASE}/{page_id or 'me'}",
                            params={"fields": "name", "access_token": page_token})
        if r.status_code == 200:
            return {"ok": True, "name": r.json().get("name", "")}
        return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
