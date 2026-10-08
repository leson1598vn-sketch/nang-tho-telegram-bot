-- Schema for the Nàng Thơ affiliate dashboard bot.
-- Applied automatically on startup (db.py). Works on Postgres and SQLite
-- (db.py adapts types for SQLite).

CREATE TABLE IF NOT EXISTS videos (
  id SERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  product_name TEXT NOT NULL,
  price_vnd INT,
  fb_video_id TEXT,
  fb_post_url TEXT,
  affiliate_link TEXT,
  published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status TEXT NOT NULL DEFAULT 'published'
);

CREATE TABLE IF NOT EXISTS fb_snapshots (
  id SERIAL PRIMARY KEY,
  video_id INT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  plays BIGINT DEFAULT 0,
  reach BIGINT DEFAULT 0,
  avg_watch_ms BIGINT DEFAULT 0,
  likes INT DEFAULT 0,
  comments INT DEFAULT 0,
  shares INT DEFAULT 0,
  length_sec INT DEFAULT 0
);
CREATE INDEX IF NOT EXISTS fb_snapshots_video_time ON fb_snapshots(video_id, fetched_at DESC);

CREATE TABLE IF NOT EXISTS shopee_daily (
  id SERIAL PRIMARY KEY,
  day DATE NOT NULL,
  product_name TEXT NOT NULL,
  clicks INT NOT NULL DEFAULT 0,
  orders INT NOT NULL DEFAULT 0,
  commission_vnd INT NOT NULL DEFAULT 0,
  source TEXT NOT NULL DEFAULT 'api',
  UNIQUE(day, product_name)
);

CREATE TABLE IF NOT EXISTS pending_videos (
  id SERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  product_name TEXT,
  preview_file_id TEXT,
  preview_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status TEXT NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
