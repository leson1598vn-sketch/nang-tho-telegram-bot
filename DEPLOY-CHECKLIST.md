# Checklist deploy Nàng Thơ Dashboard Bot (cập nhật 2026-10-09)

## Đã có
- [x] Code bot: ~/workspace/affiliate-video/telegram-bot/ (test pass)
- [x] Telegram bot token mới: user giữ (lấy lại qua @BotFather → /mybots → API Token)
- [x] ADMIN_CHAT_ID: 7879404182

## Còn thiếu (làm khi deploy)
- [ ] DATABASE_URL — tạo project free tại neon.tech → copy connection string
- [ ] FB_PAGE_TOKEN — long-lived Page token (read_insights) cho page 1367543446440909 (optional)
- [ ] SHOPEE_APPID / SHOPEE_SECRET (optional — chưa có thì dùng /nhapdon tay)
- [ ] WEBHOOK_URL — có sau khi deploy Render xong

## Các bước deploy (chi tiết trong README.md)
1. Push thư mục telegram-bot lên GitHub
2. Render → New+ → Blueprint → chọn repo (dùng render.yaml có sẵn)
3. Điền env vars (ADMIN_CHAT_ID, TELEGRAM_BOT_TOKEN, DATABASE_URL, ...)
4. Deploy → copy URL service → điền WEBHOOK_URL → Manual Deploy lại 1 lần
5. cron-job.org: GET https://<service>/health mỗi 10 phút (chống Render free sleep)
