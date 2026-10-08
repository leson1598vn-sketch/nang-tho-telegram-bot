"""Database layer: Postgres (asyncpg) when DATABASE_URL is set, else local SQLite.

Queries are written with Postgres $1-style placeholders; they are converted
to ? automatically for SQLite. Timestamps are stored as TIMESTAMPTZ in
Postgres and ISO-8601 strings in SQLite.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
TZ = ZoneInfo("Asia/Ho_Chi_Minh")

_PG_PH = re.compile(r"\$\d+")


def _adapt_sqlite(sql: str) -> str:
    sql = sql.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
    sql = sql.replace("TIMESTAMPTZ", "TEXT")
    sql = sql.replace("BIGINT", "INTEGER")
    sql = re.sub(r"\bINT\b", "INTEGER", sql)
    sql = re.sub(r"\bDATE\b", "TEXT", sql)
    sql = sql.replace("DEFAULT NOW()", "DEFAULT (datetime('now'))")
    return sql


def parse_ts(v) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=TZ)
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=TZ)


def parse_day(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, (datetime, date)):
        return v.isoformat()[:10]
    return str(v)[:10]


def to_date(v) -> date | None:
    """Return a real date object for DB query params (asyncpg needs date, not str)."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


class DB:
    def __init__(self, database_url: str = ""):
        self.database_url = (database_url or "").strip()
        self.is_pg = bool(self.database_url)
        self._pool = None
        self._conn = None

    @property
    def backend(self) -> str:
        return "postgres" if self.is_pg else "sqlite"

    # ---------------- lifecycle ----------------
    async def connect(self) -> None:
        if self.is_pg:
            import asyncpg

            self._pool = await asyncpg.create_pool(
                self.database_url, min_size=1, max_size=5, command_timeout=30
            )
        else:
            import aiosqlite

            self._conn = await aiosqlite.connect("bot.db")
            self._conn.row_factory = aiosqlite.Row
            await self._conn.execute("PRAGMA foreign_keys = ON;")
            await self._conn.execute("PRAGMA journal_mode = WAL;")
            await self._conn.commit()

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
        if self._conn:
            await self._conn.close()

    async def init_schema(self) -> None:
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        if self.is_pg:
            async with self._pool.acquire() as c:
                await c.execute(sql)
        else:
            await self._conn.executescript(_adapt_sqlite(sql))
            await self._conn.commit()

    async def ping(self) -> None:
        await self._fetchval("SELECT 1")

    # ---------------- low level ----------------
    def _q(self, query: str) -> str:
        return query if self.is_pg else _PG_PH.sub("?", query)

    async def _execute(self, query, *args):
        if self.is_pg:
            async with self._pool.acquire() as c:
                return await c.execute(query, *args)
        cur = await self._conn.execute(self._q(query), args)
        await self._conn.commit()
        return cur

    async def _fetch(self, query, *args) -> list[dict]:
        if self.is_pg:
            async with self._pool.acquire() as c:
                rows = await c.fetch(query, *args)
            return [dict(r) for r in rows]
        cur = await self._conn.execute(self._q(query), args)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in await cur.fetchall()]
        await cur.close()
        return rows

    async def _fetchrow(self, query, *args) -> dict | None:
        rows = await self._fetch(query, *args)
        return rows[0] if rows else None

    async def _fetchval(self, query, *args):
        row = await self._fetchrow(query, *args)
        return next(iter(row.values())) if row else None

    def _ts(self, v=None):
        v = parse_ts(v) if v is not None else datetime.now(TZ)
        return v if self.is_pg else v.isoformat()

    # ---------------- videos ----------------
    async def add_video(self, *, title: str, product_name: str, price_vnd: int | None = None,
                        fb_video_id: str | None = None, fb_post_url: str | None = None,
                        affiliate_link: str | None = None, published_at=None) -> int:
        row = await self._fetchrow(
            "INSERT INTO videos (title, product_name, price_vnd, fb_video_id, fb_post_url,"
            " affiliate_link, published_at) VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id",
            title, product_name, price_vnd, fb_video_id, fb_post_url,
            affiliate_link, self._ts(published_at),
        )
        return int(row["id"])

    async def list_videos(self, limit: int = 5, offset: int = 0) -> list[dict]:
        return await self._fetch(
            "SELECT * FROM videos ORDER BY published_at DESC LIMIT $1 OFFSET $2", limit, offset)

    async def count_videos(self) -> int:
        return int(await self._fetchval("SELECT COUNT(*) FROM videos") or 0)

    async def get_video(self, vid: int) -> dict | None:
        return await self._fetchrow("SELECT * FROM videos WHERE id=$1", vid)

    async def videos_since(self, since: datetime) -> list[dict]:
        return await self._fetch(
            "SELECT * FROM videos WHERE published_at >= $1 ORDER BY published_at DESC",
            self._ts(since))

    async def delete_video(self, vid: int) -> None:
        await self._execute("DELETE FROM fb_snapshots WHERE video_id=$1", vid)
        await self._execute("DELETE FROM videos WHERE id=$1", vid)

    # ---------------- fb snapshots ----------------
    async def add_snapshot(self, video_id: int, *, plays: int = 0, reach: int = 0,
                           avg_watch_ms: int = 0, likes: int = 0, comments: int = 0,
                           shares: int = 0, length_sec: int = 0) -> None:
        await self._execute(
            "INSERT INTO fb_snapshots (video_id, plays, reach, avg_watch_ms, likes,"
            " comments, shares, length_sec) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
            video_id, plays, reach, avg_watch_ms, likes, comments, shares, length_sec)

    async def latest_snapshot(self, video_id: int) -> dict | None:
        return await self._fetchrow(
            "SELECT * FROM fb_snapshots WHERE video_id=$1 ORDER BY fetched_at DESC LIMIT 1",
            video_id)

    async def snapshot_count(self) -> int:
        return int(await self._fetchval("SELECT COUNT(*) FROM fb_snapshots") or 0)

    # ---------------- shopee daily ----------------
    async def upsert_shopee_daily(self, day, product_name: str, clicks: int = 0,
                                 orders: int = 0, commission_vnd: int = 0,
                                 source: str = "api") -> None:
        await self._execute(
            "INSERT INTO shopee_daily (day, product_name, clicks, orders, commission_vnd, source)"
            " VALUES ($1,$2,$3,$4,$5,$6)"
            " ON CONFLICT (day, product_name) DO UPDATE SET"
            " clicks=excluded.clicks, orders=excluded.orders,"
            " commission_vnd=excluded.commission_vnd, source=excluded.source",
            to_date(day), product_name, int(clicks), int(orders),
            int(commission_vnd), source)

    async def shopee_range(self, day_from, day_to) -> list[dict]:
        return await self._fetch(
            "SELECT day, product_name, clicks, orders, commission_vnd, source FROM shopee_daily"
            " WHERE day >= $1 AND day <= $2 ORDER BY day DESC",
            to_date(day_from), to_date(day_to))

    async def product_names(self) -> list[str]:
        rows = await self._fetch(
            "SELECT product_name FROM videos UNION SELECT product_name FROM shopee_daily"
            " ORDER BY product_name")
        return [r["product_name"] for r in rows if r["product_name"]]

    # ---------------- pending approval ----------------
    async def add_pending(self, *, title: str, product_name: str | None = None,
                         preview_file_id: str | None = None,
                         preview_url: str | None = None) -> int:
        row = await self._fetchrow(
            "INSERT INTO pending_videos (title, product_name, preview_file_id, preview_url)"
            " VALUES ($1,$2,$3,$4) RETURNING id",
            title, product_name, preview_file_id, preview_url)
        return int(row["id"])

    async def list_pending(self) -> list[dict]:
        return await self._fetch(
            "SELECT * FROM pending_videos WHERE status='pending' ORDER BY created_at DESC")

    async def get_pending(self, pid: int) -> dict | None:
        return await self._fetchrow("SELECT * FROM pending_videos WHERE id=$1", pid)

    async def set_pending_status(self, pid: int, status: str) -> None:
        await self._execute("UPDATE pending_videos SET status=$1 WHERE id=$2", status, pid)

    # ---------------- settings ----------------
    async def get_setting(self, key: str, default: str = "") -> str:
        v = await self._fetchval("SELECT value FROM settings WHERE key=$1", key)
        return v if v is not None else default

    async def set_setting(self, key: str, value: str) -> None:
        await self._execute(
            "INSERT INTO settings (key, value) VALUES ($1,$2)"
            " ON CONFLICT (key) DO UPDATE SET value=excluded.value",
            key, str(value))
