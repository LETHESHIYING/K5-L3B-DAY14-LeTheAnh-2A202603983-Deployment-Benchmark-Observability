# Deployment Information

> ⚠️ **CHƯA DEPLOY.** File này là khung đã chuẩn bị sẵn. Phải đăng nhập Railway/Render bằng tài khoản cá nhân
> mới deploy được, nên các chỗ đánh dấu `TODO` bên dưới cần bạn điền sau khi deploy. Không điền URL giả.

## Public URL

TODO: `https://<tên-service>.up.railway.app` (hoặc `https://<tên-service>.onrender.com`)

## Platform

TODO: Railway / Render (chọn một)

Agent là **`06-lab-complete/`** (Part 6). Cấu hình deploy đã có sẵn:
- Railway: `06-lab-complete/railway.toml` (builder `DOCKERFILE`, `healthcheckPath = "/health"`)
- Render: `06-lab-complete/render.yaml` (web service Docker + Key Value làm Redis, secret dùng `generateValue`)

## Các bước deploy (Railway)

```bash
npm i -g @railway/cli
railway login
cd 06-lab-complete
railway init
# Thêm một service Redis trên dashboard Railway, rồi đặt biến cho service agent:
railway variables set AGENT_API_KEY=<giá-trị-bí-mật>
railway variables set REDIS_URL=<URL Redis do Railway cấp>
railway up
railway domain          # nhận public URL
```

Kiểm `GET /ready` trả 200 trước khi chụp ảnh (nghĩa là Redis đã nối được).

## Test Commands

> Thay `<URL>` và `<KEY>` bằng giá trị thật. **Không dán key thật vào file này.**

### Health Check

```bash
curl https://<URL>/health
# Expected: {"status":"ok","uptime_seconds":...,"environment":"production"}
curl https://<URL>/ready
# Expected: {"ready":true}
```

### Không có API key → 401

```bash
curl -i -X POST https://<URL>/ask -H "Content-Type: application/json" -d '{"question":"Hello"}'
# Expected: HTTP 401
```

### Có API key → 200

```bash
curl -X POST https://<URL>/ask \
  -H "X-API-Key: <KEY>" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

### Rate limiting → 429

```bash
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code} " -X POST https://<URL>/ask \
    -H "X-API-Key: <KEY>" -H "Content-Type: application/json" -d '{"question":"test"}'
done
# Expected: 200 ... 200 429 429 ...  (mặc định 10 request/phút)
```

### Kiểm bằng script chấm

```bash
python check_production_ready.py --public-url https://<URL>
```

## Environment Variables Set

| Biến | Ghi chú |
|------|---------|
| `PORT` | Platform tự cấp; Dockerfile lắng nghe `${PORT:-8000}` |
| `ENVIRONMENT` | `production` |
| `AGENT_API_KEY` | Secret, đặt trong dashboard (không commit) |
| `REDIS_URL` | URL Redis do platform cấp |
| `RATE_LIMIT_PER_MINUTE` | Mặc định `10` |
| `DAILY_BUDGET_USD` / `MONTHLY_BUDGET_USD` | Mặc định `1.0` / `10.0` |

## Screenshots

TODO: chụp và lưu vào thư mục `screenshots/`, rồi đổi các link dưới đây cho khớp:

- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
