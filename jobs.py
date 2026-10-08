"""Scheduled jobs: FB snapshot collection + daily/weekly reports.

Report text builders live here (not in handlers) so both the scheduler
and the on-demand menu buttons share the same code.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

import fb_client
from db import TZ, parse_day
from formatters import code_table, fmt_int, fmt_num, fmt_vnd, short

log = logging.getLogger("jobs")
SNAPSHOT_DAYS = 60


def _esc(s) -> str:
    import html
    return html.escape(str(s or ""), quote=False)


# ---------------- shared builders ----------------
async def build_overview_text(db, cfg, days: int, label: str) -> str:
    since = datetime.now(TZ) - timedelta(days=days)
    videos = await db.videos_since(since)

    plays = reach = likes = comments = shares = 0
    per: list[tuple[str, int]] = []
    for v in videos:
        s = await db.latest_snapshot(v["id"]) or {}
        p = int(s.get("plays") or 0)
        plays += p
        reach += int(s.get("reach") or 0)
        likes += int(s.get("likes") or 0)
        comments += int(s.get("comments") or 0)
        shares += int(s.get("shares") or 0)
        per.append((v["title"], p))
    per.sort(key=lambda x: x[1], reverse=True)

    today = datetime.now(TZ).date()
    day_from = (today - timedelta(days=days - 1)).isoformat()
    rows = await db.shopee_range(day_from, today.isoformat())
    clicks = sum(int(r["clicks"] or 0) for r in rows)
    orders = sum(int(r["orders"] or 0) for r in rows)
    comm = sum(int(r["commission_vnd"] or 0) for r in rows)

    lines = [
        f"📊 <b>Tổng quan — {_esc(label)}</b>",
        f"🎬 {len(videos)} video",
        "",
        f"👁 Lượt phát: <b>{fmt_num(plays)}</b>",
        f"👥 Reach: <b>{fmt_num(reach)}</b>",
        f"❤️ Like: <b>{fmt_num(likes)}</b>   💬 Comment: <b>{fmt_num(comments)}</b>"
        f"   🔁 Share: <b>{fmt_num(shares)}</b>",
        "",
        f"🖱 Click affiliate: <b>{fmt_num(clicks)}</b>",
        f"🛒 Đơn: <b>{fmt_num(orders)}</b>",
        f"💰 Hoa hồng ước tính: <b>{fmt_vnd(comm)}</b>",
    ]
    if per:
        lines += ["", "<b>🏆 Top video:</b>"]
        for i, (t, p) in enumerate(per[:3], 1):
            lines.append(f"{i}. {_esc(short(t, 30))} — 👁 {fmt_num(p)}")
    else:
        lines += ["", "<i>Chưa có video nào trong khoảng này.</i>"]
    if not cfg.shopee_configured:
        lines += ["", "⚠️ <i>Chưa kết nối Shopee API — số affiliate từ nhập tay (/nhapdon).</i>"]
    return "\n".join(lines)


async def build_daily_report_text(db, cfg) -> str:
    today = datetime.now(TZ).date()
    yday = (today - timedelta(days=1)).isoformat()
    rows = await db.shopee_range(yday, yday)
    clicks = sum(int(r["clicks"] or 0) for r in rows)
    orders = sum(int(r["orders"] or 0) for r in rows)
    comm = sum(int(r["commission_vnd"] or 0) for r in rows)

    new_vids = [v for v in await db.videos_since(datetime.now(TZ) - timedelta(days=1))]
    lines = [
        f"📅 <b>Báo cáo ngày {parse_day(yday)[8:10]}/{parse_day(yday)[5:7]}</b>",
        "",
        f"🖱 Click: <b>{fmt_int(clicks)}</b>   🛒 Đơn: <b>{fmt_int(orders)}</b>",
        f"💰 Hoa hồng ước tính: <b>{fmt_vnd(comm)}</b>",
    ]
    if rows:
        by_prod: dict[str, list[int]] = {}
        for r in rows:
            b = by_prod.setdefault(r["product_name"] or "?", [0, 0, 0])
            b[0] += int(r["clicks"] or 0)
            b[1] += int(r["orders"] or 0)
            b[2] += int(r["commission_vnd"] or 0)
        lines += ["", "<b>Theo sản phẩm:</b>",
                  code_table(["Sản phẩm", "Click", "Đơn", "HH"],
                             [[short(p, 16), fmt_int(c), fmt_int(o), fmt_vnd(m)]
                              for p, (c, o, m) in sorted(by_prod.items(),
                                                         key=lambda x: -x[1][2])])]
    if new_vids:
        lines += ["", f"<b>🎬 Video mới hôm qua ({len(new_vids)}):</b>"]
        for v in new_vids[:5]:
            s = await db.latest_snapshot(v["id"]) or {}
            lines.append(f"• {_esc(short(v['title'], 32))} — 👁 {fmt_num(s.get('plays'))}")
    lines += ["", "💡 <i>Hoa hồng ước tính — Shopee duyệt & đối soát sau.</i>"]
    return "\n".join(lines)


async def build_weekly_report_text(db, cfg) -> str:
    week = await build_overview_text(db, cfg, 7, "7 ngày qua")
    today = datetime.now(TZ).date()
    day_from = (today - timedelta(days=6)).isoformat()
    rows = await db.shopee_range(day_from, today.isoformat())
    by_day: dict[str, list[int]] = {}
    for r in rows:
        d = parse_day(r["day"])
        b = by_day.setdefault(d, [0, 0, 0])
        b[0] += int(r["clicks"] or 0)
        b[1] += int(r["orders"] or 0)
        b[2] += int(r["commission_vnd"] or 0)
    table = ""
    if by_day:
        table = ("\n\n<b>Hoa hồng theo ngày:</b>\n" + code_table(
            ["Ngày", "Click", "Đơn", "Hoa hồng"],
            [[d[5:], fmt_int(c), fmt_int(o), fmt_vnd(m)]
             for d, (c, o, m) in sorted(by_day.items())]))
    header = "📆 <b>Báo cáo tuần</b>\n"
    return header + week.replace("📊 <b>Tổng quan — 7 ngày qua</b>", "").strip() + table


# ---------------- senders ----------------
async def _send_to_admins(app, text: str) -> None:
    for admin_id in app.bot_data["config"].admin_chat_ids:
        try:
            await app.bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception as e:
            log.warning("send to admin %s failed: %s", admin_id, e)


async def send_daily_report(app) -> None:
    db, cfg = app.bot_data["db"], app.bot_data["config"]
    try:
        await _send_to_admins(app, await build_daily_report_text(db, cfg))
    except Exception as e:
        log.exception("daily report failed: %s", e)


async def send_weekly_report(app) -> None:
    db, cfg = app.bot_data["db"], app.bot_data["config"]
    try:
        await _send_to_admins(app, await build_weekly_report_text(db, cfg))
    except Exception as e:
        log.exception("weekly report failed: %s", e)


# ---------------- snapshot job ----------------
async def snapshot_job(app) -> None:
    db, cfg = app.bot_data["db"], app.bot_data["config"]
    since = datetime.now(TZ) - timedelta(days=SNAPSHOT_DAYS)
    try:
        videos = [v for v in await db.videos_since(since) if v.get("fb_video_id")]
    except Exception as e:
        log.warning("snapshot: list videos failed: %s", e)
        return

    sem = asyncio.Semaphore(3)

    async def one(v: dict) -> None:
        async with sem:
            try:
                m = await fb_client.fetch_reel_metrics(v["fb_video_id"], cfg.fb_page_token)
                if m["ok"] or m["plays"] or m["likes"]:
                    await db.add_snapshot(
                        v["id"], plays=m["plays"], reach=m["reach"],
                        avg_watch_ms=m["avg_watch_ms"], likes=m["likes"],
                        comments=m["comments"], shares=m["shares"],
                        length_sec=m["length_sec"])
            except Exception as e:
                log.warning("snapshot video %s failed: %s", v["id"], e)

    await asyncio.gather(*(one(v) for v in videos[:50]))
    try:
        await db.set_setting("last_snapshot_at", datetime.now(TZ).isoformat())
    except Exception:
        pass
    log.info("snapshot done for %d videos", len(videos))


async def _daily_tick(app) -> None:
    if (await app.bot_data["db"].get_setting("report_daily", "on")) == "on":
        await send_daily_report(app)


async def _weekly_tick(app) -> None:
    if (await app.bot_data["db"].get_setting("report_weekly", "on")) == "on":
        await send_weekly_report(app)


def setup_scheduler(app) -> AsyncIOScheduler:
    cfg = app.bot_data["config"]
    sch = AsyncIOScheduler(timezone=cfg.timezone)
    sch.add_job(snapshot_job, IntervalTrigger(minutes=30),
                kwargs={"app": app}, id="snapshot",
                replace_existing=True, max_instances=1, coalesce=True)
    sch.add_job(_daily_tick, CronTrigger(hour=8, minute=0),
                kwargs={"app": app}, id="daily",
                replace_existing=True, max_instances=1, coalesce=True)
    sch.add_job(_weekly_tick, CronTrigger(day_of_week="mon", hour=8, minute=0),
                kwargs={"app": app}, id="weekly",
                replace_existing=True, max_instances=1, coalesce=True)
    return sch
