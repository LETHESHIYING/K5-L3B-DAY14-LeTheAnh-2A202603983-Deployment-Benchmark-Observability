# Deployment Information

> Agent của Part 6 (`06-lab-complete/`) đã được deploy lên **Render** bằng Blueprint (`06-lab-complete/render.yaml`,
> nhánh `solution-wip`). `AGENT_API_KEY` do Render tự sinh (`generateValue: true`) và **không** được ghi vào repo.

## Public URL

https://ai-agent-2aaz.onrender.com

## Platform

Render (Web Service chạy Docker + Render Key Value làm Redis, gói free)

Agent là **`06-lab-complete/`** (Part 6). Cấu hình deploy đã có sẵn:
- Railway: `06-lab-complete/railway.toml` (builder `DOCKERFILE`, `healthcheckPath = "/health"`)
- Render: `06-lab-complete/render.yaml` (web service Docker + Key Value làm Redis, secret dùng `generateValue`)

## Các bước deploy (Render)

1. Đẩy code lên GitHub (nhánh `solution-wip`).
2. Render Dashboard → **New → Blueprint** → chọn repo.
3. Blueprint Path: `06-lab-complete/render.yaml`; Branch: `solution-wip`; đặt Blueprint Name → **Apply**.
4. Render tạo 2 dịch vụ: `ai-agent` (Web Service, Docker, `rootDir: 06-lab-complete`) và `agent-redis` (Key Value).
5. `AGENT_API_KEY` tự sinh: xem ở `ai-agent` → **Environment** (không commit giá trị này).

Kiểm `GET /ready` trả 200 (nghĩa là Redis đã nối được).

## Test Commands

> Thay `ai-agent-2aaz.onrender.com` và `<KEY>` bằng giá trị thật. **Không dán key thật vào file này.**

### Health Check

```bash
curl https://ai-agent-2aaz.onrender.com/health
# Expected: {"status":"ok","uptime_seconds":...,"environment":"production"}
curl https://ai-agent-2aaz.onrender.com/ready
# Expected: {"ready":true}
```

### Không có API key → 401

```bash
curl -i -X POST https://ai-agent-2aaz.onrender.com/ask -H "Content-Type: application/json" -d '{"question":"Hello"}'
# Expected: HTTP 401
```

### Có API key → 200

```bash
curl -X POST https://ai-agent-2aaz.onrender.com/ask \
  -H "X-API-Key: <KEY>" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

### Rate limiting → 429

```bash
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code} " -X POST https://ai-agent-2aaz.onrender.com/ask \
    -H "X-API-Key: <KEY>" -H "Content-Type: application/json" -d '{"question":"test"}'
done
# Expected: 200 ... 200 429 429 ...  (mặc định 10 request/phút)
```

### Kiểm bằng script chấm

```bash
python check_production_ready.py --public-url https://ai-agent-2aaz.onrender.com
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

- [Service running](screenshots/running.png): trình duyệt mở `GET /health` của URL trên, trả 200 (đã có)
- [Deployment dashboard](screenshots/dashboard.png): trang `ai-agent` trên Render Dashboard, trạng thái Live, URL công khai và lịch sử deploy (đã có)
- [Test results](screenshots/test.png): kết quả các lệnh test ở trên, API key được lưu trong biến `$KEY` nên không hiện trong ảnh: `/health` 200, `/ask` không key 401, `/ask` có key 200 (đã có)
