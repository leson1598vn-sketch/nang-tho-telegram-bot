"""Seed SQLite sample data + verify queries.

Run:  python test_db.py
Creates ./bot.db with 3 videos, snapshots, 7 days of Shopee rows and
1 pending video, so you can try the whole UI without any real tokens.
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.pop("DATABASE_URL", None)  # force SQLite

from db import DB, TZ  # noqa: E402


async def main() -> None:
    if os.path.exists("bot.db"):
        os.remove("bot.db")
    db = DB("")
    await db.connect()
    await db.init_schema()

    v1 = await db.add_video(
        title="Hoodie nỉ form rộng unisex mặc thu đông cực xinh",
        product_name="Áo hoodie nỉ form rộng unisex",
        price_vnd=239000, fb_video_id="1586722949366870",
        fb_post_url="https://facebook.com/reel/1586722949366870/",
        affiliate_link="https://s.shopee.vn/xxxx",
        published_at=datetime.now(TZ) - timedelta(days=2))
    v2 = await db.add_video(
        title="Quần jean ống rộng nữ cạp cao hack dáng",
        product_name="Quần jean ống rộng nữ",
        price_vnd=189000, fb_video_id="1234567890",
        published_at=datetime.now(TZ) - timedelta(days=6))
    v3 = await db.add_video(
        title="Váy hoa nhí tiểu thư đi cà phê",
        product_name="Váy hoa nhí",
        price_vnd=159000,
        published_at=datetime.now(TZ) - timedelta(days=12))

    await db.add_snapshot(v1, plays=12500, reach=9800, avg_watch_ms=27000,
                          likes=640, comments=88, shares=45, length_sec=61)
    await db.add_snapshot(v2, plays=8300, reach=7100, avg_watch_ms=21000,
                          likes=402, comments=51, shares=20, length_sec=58)
    await db.add_snapshot(v3, plays=31200, reach=27000, avg_watch_ms=33000,
                          likes=1500, comments=210, shares=130, length_sec=60)

    today = datetime.now(TZ).date()
    for i in range(7):
        day = (today - timedelta(days=i)).isoformat()
        await db.upsert_shopee_daily(day, "Áo hoodie nỉ form rộng unisex",
                                     clicks=40 + i * 3, orders=2 + (i % 3),
                                     commission_vnd=30000 + i * 2500, source="manual")
        await db.upsert_shopee_daily(day, "Quần jean ống rộng nữ",
                                     clicks=25 + i * 2, orders=1 + (i % 2),
                                     commission_vnd=15000 + i * 1200, source="manual")

    pid = await db.add_pending(title="Video demo chờ duyệt", product_name="Váy hoa nhí")
    await db.set_setting("report_daily", "on")
    await db.set_setting("report_weekly", "on")

    # ---- verify ----
    assert await db.count_videos() == 3, "videos"
    assert await db.snapshot_count() == 3, "snapshots"
    assert len(await db.list_pending()) == 1, "pending"
    assert len(await db.product_names()) == 3, "products"
    rows = await db.shopee_range((today - timedelta(days=6)).isoformat(),
                                   today.isoformat())
    assert len(rows) == 14, f"shopee rows: {len(rows)}"
    s = await db.latest_snapshot(v1)
    assert s["plays"] == 12500, "latest snapshot"
    # upsert is idempotent (no duplicate rows)
    await db.upsert_shopee_daily(today.isoformat(), "Áo hoodie nỉ form rộng unisex",
                                 1, 0, 0, source="manual")
    rows2 = await db.shopee_range(today.isoformat(), today.isoformat())
    assert len([r for r in rows2
                if r["product_name"] == "Áo hoodie nỉ form rộng unisex"]) == 1, "upsert"

    print("OK: 3 video, 3 snapshot, 14 dòng Shopee, 1 video chờ duyệt (pending id"
          f" #{pid}) — bot.db sẵn sàng.")
    print("Chạy thử UI: tạo bot tại @BotFather, điền TELEGRAM_BOT_TOKEN + ADMIN_CHAT_ID")
    print("vào file .env (copy từ .env.example), rồi chạy:  python bot.py")
    print("(Chưa cần token Facebook/Shopee — bot vẫn chạy ở chế độ dữ liệu mẫu.)")
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
