# 🤖 Nàng Thơ Bot — Telegram Dashboard cho Reels Affiliate

Bot Telegram chuyên nghiệp để xem số liệu **bất cứ lúc nào**: mở Telegram → bấm nút
→ có ngay số liệu Facebook Reels + Shopee affiliate mới nhất. Không cần nhớ lệnh,
không phải đợi đến giờ báo cáo.

## ✨ Tính năng

| Nút | Chức năng |
|---|---|
| 📊 Tổng quan | Plays, reach, like, comment, share, click, đơn, hoa hồng theo Hôm nay / 7 ngày / 30 ngày + top 3 video |
| 🎬 Video | Danh sách video (phân trang) → chi tiết từng video, nút 🔄 cập nhật số liệu live |
| 🛍️ Sản phẩm | Click, đơn, tỉ lệ chuyển đổi, hoa hồng theo từng sản phẩm + video liên quan |
| 💰 Hoa hồng | Tổng ước tính + bảng theo ngày (ghi rõ "ước tính, Shopee duyệt sau") |
| ✅ Duyệt video | Hàng đợi duyệt video từ n8n (preview + nút ✅/❌) |
| ⏰ Báo cáo | Bật/tắt báo cáo ngày (08:00) & tuần (08:00 thứ Hai), gửi ngay khi cần |
| ⚙️ Hệ thống | Uptime, trạng thái DB, Facebook API, Shopee API, n8n heartbeat, version |

Lệnh dẫn từng bước: `/themvideo` (đăng ký video mới), `/nhapdon` (nhập số liệu
Shopee tay), `/xoavideo` (xóa video), `/huy` (hủy thao tác).

## 🚀 Chạy thử local (5 phút, không cần token thật)

```bash
cd ~/workspace/affiliate-video/telegram-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# 1. Nhắn @BotFather trên Telegram: /newbot -> lấy token điền vào TELEGRAM_BOT_TOKEN
# 2. Nhắn @userinfobot: /start -> lấy số Id điền vào ADMIN_CHAT_ID
# 3. Để trống WEBHOOK_URL (bot chạy chế độ polling khi test local)

python test_db.py   # tạo bot.db với dữ liệu mẫu
python bot.py       # mở Telegram, nhắn /start cho bot
```

Chưa có token Facebook/Shopee cũng chạy được — các mục đó sẽ hiện "chưa kết nối"
chứ không crash.

## 🔑 Lấy các token cho dữ liệu thật

### 1. Telegram bot token + Admin chat ID
- `@BotFather` → `/newbot` → đặt tên → copy token.
- `@userinfobot` → `/start` → copy số `Id`.

### 2. Facebook Page Access Token (dài hạn, quyền `read_insights`)
1. Vào [developers.facebook.com](https://developers.facebook.com) → tạo App (loại Business).
2. Thêm sản phẩm **Facebook Login** không cần — chỉ cần **Graph API Explorer**:
   mở [Graph API Explorer](https://developers.facebook.com/tools/explorer),
   chọn app của bạn → **User Token** → tick quyền `read_insights`, `pages_read_engagement` → Generate.
3. Đổi sang long-lived token:
   `GET /oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=SHORT_TOKEN`
4. Lấy Page token: `GET /me/accounts` → tìm page **Nàng Thơ Shopping**
   (ID `1367543446440909`) → copy `access_token` → điền vào `FB_PAGE_TOKEN`.
   Page token này thực tế không hết hạn khi app ở chế độ live.

### 3. Shopee Affiliate API (tùy chọn)
1. Đăng ký [Shopee Affiliate Program](https://shopee.vn) → vào mục API/đối tác
   để xin `appid` + `secret`.
2. Điền `SHOPEE_API_BASE_URL`, `SHOPEE_APPID`, `SHOPEE_SECRET` vào `.env`.
3. **Chưa có?** Bỏ trống cả 3 — bot tự hiện "chưa kết nối" và bạn dùng
   `/nhapdon` nhập số liệu tay mỗi ngày (vẫn lên đủ bảng thống kê).

### 4. Neon Postgres (dùng chung với n8n)
1. Tạo project miễn phí tại [neon.tech](https://neon.tech) → copy connection string.
2. Điền vào `DATABASE_URL`. Schema tự tạo khi bot khởi động.

## ☁️ Deploy lên Render (free)

1. Push thư mục này lên GitHub (riêng 1 repo hoặc subfolder).
2. Render → **New +** → **Blueprint** → chọn repo (dùng `render.yaml` có sẵn).
3. Điền các biến `sync: false` trong mục Environment.
4. Deploy xong → copy URL service (VD `https://nang-tho-telegram-bot.onrender.com`)
   → điền vào `WEBHOOK_URL` → **Manual Deploy** lại 1 lần để bot đăng ký webhook.

**Chống sleep (Render free ngủ sau 15 phút):** vào
[cron-job.org](https://cron-job.org) tạo job GET `https://<service>/health`
mỗi **10 phút**.

## 🔗 Nối với n8n

Bot mở 2 endpoint cho n8n (header `X-Webhook-Secret: <N8N_WEBHOOK_SECRET>`):

**a) Khi publish video xong → ghi vào DB** (Postgres node):
```sql
INSERT INTO videos (title, product_name, price_vnd, fb_video_id, fb_post_url, affiliate_link)
VALUES ('{{$json.title}}', '{{$json.product}}', {{$json.price}}, '{{$json.video_id}}', '{{$json.url}}', '{{$json.aff}}');
```

**b) Gửi video chờ duyệt** (HTTP Request node → `POST https://<bot>/api/pending`):
```json
{"title": "...", "product_name": "...", "preview_url": "https://...mp4"}
```
Admin bấm ✅/❌ trên Telegram; bot gọi ngược `N8N_WEBHOOK_URL` (nếu cấu hình)
với `{"pending_id": 1, "decision": "approved", ...}` để n8n đăng bài tiếp.

**c) Heartbeat** (cuối mỗi workflow → `POST https://<bot>/api/heartbeat`):
mục ⚙️ Hệ thống sẽ hiện "n8n: vừa xong / X phút trước".

## 📁 Cấu trúc

```
bot.py                 # entrypoint (webhook hoặc polling)
config.py              # đọc & kiểm tra biến môi trường
db.py                  # Postgres (asyncpg) / SQLite (aiosqlite) + CRUD
db/schema.sql          # migration, tự chạy khi khởi động
fb_client.py           # Graph API video_insights (không bao giờ crash bot)
shopee_client.py       # Shopee Affiliate API, degrade khi chưa có credentials
formatters.py          # 1.2K / 250.000 ₫ / m:ss / bảng monospace
handlers/              # menu, overview, videos, products, commission,
                       # approval, reports, system, admin_conversations
jobs.py                # snapshot 30 phút, báo cáo 08:00, builders dùng chung
api.py                 # FastAPI: /health, /webhook, /api/pending, /api/heartbeat
```

## ✅ Checklist token khi lên production

- [ ] `TELEGRAM_BOT_TOKEN` (từ @BotFather)
- [ ] `ADMIN_CHAT_ID` (từ @userinfobot)
- [ ] `WEBHOOK_URL` + `WEBHOOK_SECRET` (sau deploy Render)
- [ ] `FB_PAGE_TOKEN` (long-lived, quyền `read_insights`)
- [ ] `SHOPEE_API_BASE_URL` / `SHOPEE_APPID` / `SHOPEE_SECRET` (hoặc dùng `/nhapdon`)
- [ ] `DATABASE_URL` (Neon Postgres)
- [ ] `N8N_WEBHOOK_SECRET` (+ `N8N_WEBHOOK_URL` nếu muốn bot gọi ngược n8n)
- [ ] Keep-alive cron-job.org → `/health` mỗi 10 phút
