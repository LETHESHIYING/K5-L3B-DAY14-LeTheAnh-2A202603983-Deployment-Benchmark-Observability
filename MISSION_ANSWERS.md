# Day 14 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found

Phân tích file `01-localhost-vs-production/develop/app.py`:

1. **API key và DATABASE_URL viết cứng trong code** (dòng 17–18).
   `OPENAI_API_KEY = "sk-..."` và `DATABASE_URL = "postgresql://admin:password123@..."` nằm thẳng trong source. Push lên GitHub là lộ secret ngay, và muốn đổi key phải sửa code.
2. **Không có config management** (dòng 21–22).
   `DEBUG = True` và `MAX_TOKENS = 500` là hằng số trong code, không thể đổi theo môi trường (dev/staging/prod) nếu không sửa và build lại.
3. **Dùng `print()` thay vì logging có cấu trúc** (dòng 33, 38).
   Không có log level, không có timestamp, không ở dạng JSON nên hệ thống thu log (Loki, Datadog, ...) khó phân tích.
4. **In secret ra log** (dòng 34).
   `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` làm lộ API key vào log, mà log thường được nhiều người và nhiều hệ thống đọc được.
5. **Không có health check endpoint** (dòng 42–43).
   Không có `/health` hay `/ready`, nên platform (Railway, Render, Kubernetes) không biết agent đã crash hay chưa để tự restart.
6. **Port cố định, không đọc từ environment** (dòng 52).
   `port=8000` viết cứng. Railway/Render inject cổng qua biến `PORT`, nên app sẽ không nhận được traffic.
7. **Host chỉ là `localhost`** (dòng 51).
   Chỉ nhận kết nối từ chính máy đó. Trong container hoặc trên cloud, phải bind `0.0.0.0` thì bên ngoài mới truy cập được.
8. **`reload=True` trong lúc chạy** (dòng 53).
   Chế độ auto-reload dành cho phát triển: tốn tài nguyên, có thể khởi động lại giữa chừng và không an toàn khi production.
9. **Không xử lý graceful shutdown** (toàn file).
   Không có handler cho SIGTERM, nên khi platform dừng container thì các request đang chạy bị cắt ngang.

### Exercise 1.2: Kết quả chạy bản develop

Đã chạy `python app.py` trong `01-localhost-vs-production/develop` và gọi:

```bash
curl.exe -X POST "http://localhost:8000/ask?question=Hello"
# {"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

Bản develop nhận `question` qua query string (không nhận JSON). Mock LLM trả lời theo từ khóa (`docker`, `deploy`, `health`), câu không khớp thì chọn ngẫu nhiên một câu mặc định.

### Exercise 1.3: Comparison table

So sánh `develop/app.py` với `production/app.py` và `production/config.py`:

| Feature | Develop | Production | Why Important? |
|---------|---------|------------|----------------|
| Config | Hardcode trong code: `OPENAI_API_KEY`, `DATABASE_URL`, `DEBUG`, `MAX_TOKENS` (dòng 17–22) | Đọc từ biến môi trường qua `Settings` trong `config.py` (`os.getenv("PORT", "8000")`, `DEBUG`, `AGENT_API_KEY`, ...). Có `validate()` báo lỗi nếu thiếu `AGENT_API_KEY` khi chạy production | Không lộ secret trong source/GitHub; cùng một code chạy được ở dev/staging/prod chỉ bằng cách đổi env var; thiếu cấu hình bắt buộc thì app dừng ngay lúc khởi động (fail fast) |
| Port / Host | Cố định `host="localhost"`, `port=8000` (dòng 51–52) | `host=settings.host` (mặc định `0.0.0.0`), `port=settings.port` lấy từ `PORT` | Railway/Render inject `PORT`; `0.0.0.0` cho phép nhận kết nối từ bên ngoài container |
| Health check | Không có | `GET /health` (liveness: uptime, version, timestamp) và `GET /ready` (readiness: trả 503 khi chưa sẵn sàng) | Platform biết khi nào app chết để restart (`/health`), và load balancer biết khi nào mới được chuyển traffic vào (`/ready`) |
| Logging | `print()`, kể cả in ra API key (dòng 33–38) | `logging` với định dạng JSON, có level; log `question_length`, `client_ip`, không log secret | Log JSON dễ parse trong Datadog/Loki; có level để lọc; không làm lộ secret vào log |
| Shutdown | Không xử lý, process bị tắt đột ngột | `lifespan` shutdown + handler `SIGTERM` (dòng 39–67, 180–189): đặt `is_ready = False`, chờ request hiện tại xong rồi mới tắt | Khi deploy bản mới hoặc scale down, request đang xử lý không bị cắt ngang, người dùng không gặp lỗi |
| Debug / reload | `reload=True` luôn bật | `reload=settings.debug`, mặc định `DEBUG=false` | Reload chỉ nên bật khi phát triển, không dùng khi production |
| Giao tiếp `/ask` | Nhận `question` qua query string | Nhận JSON body, trả 422 nếu thiếu `question` | Input rõ ràng, có kiểm tra hợp lệ |

**Tự kiểm tra (anti-pattern đã được sửa):** dòng 17 của develop `OPENAI_API_KEY = "sk-hardcoded-..."` đã được thay bằng `openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))` ở `production/config.py` dòng 27.

**Kết quả chạy bản production:**

Đã chạy `python app.py` trong `01-localhost-vs-production/production`:

```bash
curl.exe -i http://localhost:8000/health
# HTTP/1.1 200 OK
# {"status":"ok","uptime_seconds":63.0,"version":"1.0.0","environment":"development","timestamp":"2026-11-26T08:11:30.003896+00:00"}

curl.exe -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question": "Hello"}'
# {"question":"Hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.","model":"gpt-4o-mini"}

curl.exe http://localhost:8000/ready
# {"ready":true}
```

Khác với bản develop: bản production có `/health` và `/ready`, nhận JSON body và trả thêm trường `model`.

## Part 2: Docker

### Exercise 2.1: Dockerfile questions

Phân tích `02-docker/develop/Dockerfile`:

1. **Base image:** `python:3.11` (dòng 8), bản Python đầy đủ nên rất nặng.
2. **Working directory:** `/app` (dòng 11, `WORKDIR /app`).
3. **Vì sao `COPY requirements.txt` trước:** Docker build theo từng layer và cache lại. Requirements ít thay đổi, còn code thì đổi liên tục. Nếu copy requirements và `pip install` trước, khi chỉ sửa code thì Docker dùng lại layer đã cài thư viện, không phải cài lại, nên build nhanh hơn rất nhiều.
4. **CMD vs ENTRYPOINT:**
   - `CMD` là lệnh *mặc định*, có thể bị ghi đè dễ dàng khi `docker run <image> <lệnh khác>`.
   - `ENTRYPOINT` là chương trình *cố định* của container; tham số đưa vào `docker run` chỉ được nối thêm phía sau, muốn thay phải dùng `--entrypoint`.
   - Dockerfile này dùng `CMD ["python", "app.py"]`.

### Exercise 2.2: Build và run bản develop

```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -d --rm --name k5-dev -p 8001:8000 my-agent:develop
curl.exe -s -X POST "http://localhost:8001/ask?question=What%20is%20Docker"
# {"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

(Map cổng host 8001 vì cổng 8000 có thể đang bị chiếm bởi server khác.)
Bản develop trong container nhận `question` qua query. Gửi JSON body như trong `CODE_LAB.md` thì bị lỗi 422 (`Field required`, `loc: query.question`).

### Exercise 2.3: Multi-stage build và so sánh kích thước

`02-docker/production/Dockerfile`:

- **Stage 1 (builder):** dùng `python:3.11-slim`, cài `gcc` và `libpq-dev`, rồi `pip install --user` các thư viện. Stage này chỉ để *build*, không dùng để chạy.
- **Stage 2 (runtime):** cũng là `python:3.11-slim`, chỉ copy thư mục thư viện đã cài (`/root/.local`) và mã nguồn từ stage 1. Có thêm user không phải root (`appuser`), `HEALTHCHECK` và chạy `uvicorn` với 2 worker.
- **Vì sao nhỏ hơn:** (1) base `slim` thay vì bản đầy đủ; (2) gcc, header, cache apt và công cụ build ở stage 1 không đi vào image cuối; (3) chỉ giữ lại những gì cần để chạy.

Kích thước đo bằng `docker images my-agent` trên máy của mình:

| Image | DISK USAGE | CONTENT SIZE (nén) |
|-------|-----------:|-------------------:|
| `my-agent:develop` | 1.67 GB (~1710 MB) | 426 MB |
| `my-agent:advanced` | 240 MB | 57.4 MB |

- Develop: ~1710 MB
- Production: 240 MB
- Difference: giảm khoảng **86%** (240 / 1710 ≈ 14%). Tính theo content size thì giảm khoảng 87% (57.4 / 426 ≈ 13.5%).

Docker Desktop bản mới hiển thị hai cột; mình dùng *DISK USAGE* (dung lượng thực trên đĩa) làm số chính. Cả hai đều dưới mức 500 MB mà bài yêu cầu cho image production.

### Exercise 2.4: Docker Compose stack

Đọc `02-docker/production/docker-compose.yml`. Stack có **4 service** trong cùng mạng nội bộ `internal`:

| Service | Image | Vai trò |
|---------|-------|---------|
| `nginx` | `nginx:alpine` | Reverse proxy / load balancer. **Cổng duy nhất mở ra ngoài** (80, 443). Giới hạn 10 req/giây mỗi IP, thêm security headers |
| `agent` | build từ `02-docker/production/Dockerfile` (stage `runtime`) | FastAPI agent. Không publish cổng, chỉ nhận request qua Nginx |
| `redis` | `redis:7-alpine` | Bộ nhớ dùng chung cho session và rate limiting (có volume `redis_data`) |
| `qdrant` | `qdrant/qdrant:v1.9.0` | Vector database cho RAG (có volume `qdrant_data`) |

Sơ đồ:

```
                    (cổng 80/443 mở ra ngoài)
  Client ───────────────▶ nginx ──────────▶ agent:8000
                                              │   │
                                 redis:6379 ◀─┘   └─▶ qdrant:6333
          └──────── mạng nội bộ "internal" (bridge) ────────┘
```

Cách các service giao tiếp:
- Chúng gọi nhau **bằng tên service** qua Docker DNS (ví dụ `REDIS_URL=redis://redis:6379/0`, `QDRANT_URL=http://qdrant:6333`, Nginx `proxy_pass http://agent_backend` với `server agent:8000`).
- `agent` có `depends_on` redis và qdrant với `condition: service_healthy`, nên chỉ khởi động khi hai service đó đã healthy. `nginx` chờ `agent`.
- Chỉ `nginx` publish cổng; `agent`, `redis`, `qdrant` không thể truy cập trực tiếp từ bên ngoài.

Chạy stack (cần tạo `.env.local` rỗng; dùng `-p` riêng để tránh trùng tên project với các bài khác):

```bash
touch .env.local
docker compose -p k5-day14-docker up -d --build
docker compose -p k5-day14-docker ps
# agent   Up (healthy)   8000/tcp
# nginx   Up             0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
# qdrant  Up (healthy)   6333-6334/tcp
# redis   Up (healthy)   6379/tcp
```

Test qua Nginx:

```bash
curl.exe -i http://localhost/health
# HTTP/1.1 200 OK   (Server: nginx, X-Frame-Options: DENY, X-Content-Type-Options: nosniff, ...)
# {"status":"ok","uptime_seconds":11.1,"version":"2.0.0","timestamp":"2026-11-26T08:48:51.483346"}

curl.exe -X POST http://localhost/ask -H "Content-Type: application/json" -d '{"question": "Explain microservices"}'
# {"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}

curl.exe http://localhost/ready
# {"ready":true}

curl.exe -m 3 http://localhost:8000/health
# không kết nối được (HTTP 000): agent không mở cổng trực tiếp, chỉ truy cập được qua Nginx
```

Sau khi test đã dừng stack bằng `docker compose -p k5-day14-docker down`.

## Part 3: Cloud Deployment

### Exercise 3.1 / 3.2: Deploy agent Part 6 lên Railway hoặc Render

> **CHƯA LÀM — cần tài khoản cloud của bạn.** Đây là bước duy nhất mình không thể làm thay: phải đăng nhập Railway/Render bằng tài khoản của bạn (`railway login` mở trình duyệt), tạo Redis trên nền tảng và chụp màn hình. Mọi cấu hình cần thiết đã sẵn sàng trong `06-lab-complete/` (`railway.toml`, `render.yaml`, Dockerfile lắng nghe `${PORT}`).
>
> Việc cần làm (xem `DEPLOYMENT.md` để điền URL thật và dán ảnh):
> 1. Railway: `cd 06-lab-complete && railway login && railway init`, tạo thêm một Redis, đặt `REDIS_URL`, `AGENT_API_KEY` cho service agent, rồi `railway up` và `railway domain`.
> 2. Kiểm `GET <URL>/ready` trả 200, rồi chạy `python check_production_ready.py --public-url <URL>`.

### Exercise 3.3: Cloud Run (chỉ đọc, không cần deploy)

Pipeline CI/CD trong `cloudbuild.yaml` chạy tự động mỗi lần push lên `main`, gồm 4 bước nối tiếp nhau (`waitFor`): **(1) test** chạy `pytest` trong `python:3.11-slim`; **(2) build** image Docker, gắn hai tag `:$COMMIT_SHA` (để truy vết/rollback) và `:latest`, dùng `--cache-from` để tái sử dụng layer; **(3) push** image lên Container Registry; **(4) deploy** lên Cloud Run bằng `gcloud run deploy` với image đúng commit vừa build. Nếu test fail thì các bước sau không chạy nên code lỗi không bao giờ được deploy.

`service.yaml` là định nghĩa dịch vụ dưới dạng code (IaC): tự scale từ 1 đến 10 instance (`minScale: 1` tránh cold start), mỗi instance nhận tối đa 80 request đồng thời, giới hạn 1 CPU / 512 MiB, timeout 60 giây. Secret (`OPENAI_API_KEY`, `AGENT_API_KEY`) lấy từ **Secret Manager** qua `secretKeyRef`, không viết thẳng giá trị. `livenessProbe` gọi `/health` (restart khi chết) và `startupProbe` gọi `/ready` (chỉ nhận traffic khi đã sẵn sàng), đúng hai endpoint đã làm ở Part 5 và 6.

## Part 4: API Security

### Exercise 4.1: API Key authentication (`04-api-gateway/develop/app.py`)

- **API key được check ở đâu?** Hàm `verify_api_key` (dòng 39–54) đọc header `X-API-Key` và so với biến `API_KEY` lấy từ env `AGENT_API_KEY` (dòng 35). Endpoint `/ask` bảo vệ bằng `Depends(verify_api_key)` (dòng 70). `/` và `/health` để công khai.
- **Sai key thì sao?** Thiếu key → **401 Unauthorized**; có key nhưng sai → **403 Forbidden**.
- **Rotate key thế nào?** Đổi giá trị biến môi trường `AGENT_API_KEY` rồi restart service, không cần sửa code. (Lý tưởng: cho phép hai key cùng hợp lệ trong thời gian chuyển đổi để client cũ không bị gián đoạn.)

Test (server chạy với `AGENT_API_KEY=secret-key-123`):

```bash
curl.exe -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question": "Hello"}'
# HTTP/1.1 401 Unauthorized
# {"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

curl.exe -i -X POST http://localhost:8000/ask -H "X-API-Key: wrong" -H "Content-Type: application/json" -d '{"question": "Hello"}'
# HTTP/1.1 403 Forbidden
# {"detail":"Invalid API key."}

curl.exe -i -X POST http://localhost:8000/ask -H "X-API-Key: secret-key-123" -H "Content-Type: application/json" -d '{"question": "Hello"}'
# HTTP/1.1 200 OK
# {"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

### Exercise 4.2: JWT authentication (`04-api-gateway/production`)

JWT flow (từ `auth.py`): client gửi `username/password` tới `POST /auth/token` → server kiểm tra (`authenticate_user`) rồi ký token HS256 bằng `JWT_SECRET` (chứa `sub`, `role`, `iat`, `exp`, hết hạn sau 60 phút) → client gửi token trong header `Authorization: Bearer <token>` → `verify_token` giải mã và kiểm tra chữ ký/hạn, không cần tra database mỗi request (stateless). Token hết hạn → 401, token sai → 403.

Dùng tài khoản `student / demo123` (endpoint là `/auth/token`, không phải `/token`):

```bash
curl.exe -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Explain JWT"}'
# HTTP/1.1 401 Unauthorized
# {"detail":"Authentication required. Include: Authorization: Bearer <token>"}

curl.exe -X POST http://localhost:8000/auth/token -H "Content-Type: application/json" -d '{"username":"student","password":"demo123"}'
# {"access_token":"eyJhbGciOiJIUzI1NiIs...<đã che>","token_type":"bearer","expires_in_minutes":60,...}

curl.exe -i -X POST http://localhost:8000/ask -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" -d '{"question":"Explain JWT"}'
# HTTP/1.1 200 OK
# {"question":"Explain JWT","answer":"...","usage":{"requests_remaining":9,"budget_remaining_usd":2.1e-05}}

curl.exe -i -X POST http://localhost:8000/ask -H "Authorization: Bearer abc.def.ghi" ...
# HTTP/1.1 403 Forbidden   (token giả)
```

### Exercise 4.3: Rate limiting (`rate_limiter.py`)

- **Algorithm:** *Sliding window counter*. Mỗi user có một `deque` chứa timestamp các request; mỗi lần gọi bỏ các timestamp cũ hơn 60 giây, nếu số còn lại ≥ giới hạn thì trả 429.
- **Limit:** user thường **10 request/phút** (`rate_limiter_user`), admin **100 request/phút** (`rate_limiter_admin`).
- **Admin bypass:** không bỏ hẳn giới hạn mà dùng một limiter riêng với trần cao hơn: `app.py` chọn `rate_limiter_admin` khi `role == "admin"` (dòng 141).
- Lưu ý: bộ đếm nằm trong RAM của từng process, nên khi chạy nhiều instance thì mỗi instance đếm riêng. Đó là lý do Part 6 chuyển sang Redis.

Test: gọi liên tục với token `student` (tính cả lần gọi 200 ở 4.2, lần thứ 10 trong phút bị chặn):

```text
#1..#9 -> 200
#10 -> 429
#11 -> 429
#12 -> 429
```

```bash
curl.exe -i -X POST http://localhost:8000/ask -H "Authorization: Bearer <TOKEN>" ...
# HTTP/1.1 429 Too Many Requests
# x-ratelimit-limit: 10
# x-ratelimit-remaining: 0
# retry-after: 54
# {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":54}}
```

Với tài khoản `teacher` (role admin): 15 request liên tiếp đều trả 200. `GET /admin/stats` với `student` trả 403, với `teacher` trả 200.

### Exercise 4.4: Cost guard

`04-api-gateway/production/cost_guard.py` hiện là bản **in-memory**: mỗi user có ngân sách **$1/ngày**, toàn hệ thống **$10/ngày**. `check_budget` được gọi *trước* khi gọi LLM: vượt ngân sách toàn cục → 503, vượt ngân sách user → 402; gần 80% thì ghi cảnh báo. Sau khi gọi LLM, `record_usage` cộng token và chi phí đã dùng (tính theo giá token input/output).

Đề bài 4.4 yêu cầu phiên bản **$10/tháng mỗi user, lưu trong Redis**. Cách làm:

1. **Khóa theo tháng:** `budget:{user_id}:{YYYY-MM}`. Sang tháng mới sẽ là khóa mới nên tự "reset" mà không cần job dọn dẹp.
2. **Lưu trong Redis, không lưu trong RAM:** mọi instance đọc/ghi cùng một nơi, nên chi phí không bị đếm rải rác và không mất khi restart (stateless).
3. **Cộng dồn nguyên tử bằng `INCRBYFLOAT`** để hai request đồng thời không ghi đè lên nhau.
4. **Kiểm tra trước khi gọi LLM:** nếu `chi phí hiện tại + chi phí ước tính > $10` thì từ chối (402), ngược lại cộng vào khóa.
5. **Đặt hạn cho khóa** (`EXPIRE` ~32 ngày) để Redis tự dọn các tháng cũ.

```python
def check_budget(user_id: str, estimated_cost: float) -> bool:
    month_key = datetime.now().strftime("%Y-%m")
    key = f"budget:{user_id}:{month_key}"
    current = float(r.get(key) or 0)
    if current + estimated_cost > 10:
        return False
    r.incrbyfloat(key, estimated_cost)
    r.expire(key, 32 * 24 * 3600)
    return True
```

Đây là đáp án mẫu của đề; phần cài đặt thật (`app/cost_guard.py` dùng Redis) sẽ làm ở Part 6. Rate limit bảo vệ *tốc độ* gọi, cost guard bảo vệ *tiền*: cần cả hai vì một user có thể gọi chậm nhưng mỗi câu hỏi rất dài và tốn kém.

## Part 5: Scaling & Reliability

### Exercise 5.1: Health checks (`05-scaling-reliability/develop/app.py`)

Bản develop đã cài sẵn hai endpoint:

- `GET /health` (liveness, "process còn sống không?"): trả `status`, `uptime_seconds`, `version`, `checks`. Nếu trả non-200 hoặc timeout thì platform restart container.
- `GET /ready` (readiness, "có nhận traffic được chưa?"): dựa vào cờ `_is_ready`; trả **503** khi đang khởi động hoặc đang shutdown, trả 200 khi sẵn sàng. Load balancer dùng nó để quyết định có route request vào instance này không.

Chạy trong container Linux (`python:3.11-slim`, map cổng 8001):

```text
GET /health -> 200 {"status":"ok","uptime_seconds":1.7,"version":"1.0.0",...}
GET /ready  -> 200 {"ready":true,"in_flight_requests":1}
POST /ask?question=Hello -> 200 {"answer":"..."}
```

### Exercise 5.2: Graceful shutdown

Cơ chế trong `develop/app.py`:

1. Có một middleware đếm số request đang xử lý (`_in_flight_requests`).
2. Khi nhận **SIGTERM**, uvicorn chạy phần shutdown của `lifespan`: đặt `_is_ready = False` (để `/ready` trả 503, load balancer ngừng gửi request mới), rồi **chờ tối đa 30 giây** cho tới khi `_in_flight_requests == 0`, sau đó mới thoát. `uvicorn.run(..., timeout_graceful_shutdown=30)` cho phép việc chờ này.
3. Hàm `handle_sigterm` chỉ ghi log; việc dừng thật do uvicorn đảm nhiệm.

Windows không gửi được SIGTERM nên mình chạy app trong container Linux rồi `docker stop` (docker gửi SIGTERM). Log:

```text
INFO:     Shutting down
INFO:     Waiting for application shutdown.
... 🔄 Graceful shutdown initiated...
... ✅ Shutdown complete
INFO:     Application shutdown complete.
INFO:     Finished server process [1]
... Received signal 15 — uvicorn will handle graceful shutdown
```

(`signal 15` = SIGTERM.) Request mock chỉ mất ~0.1 giây nên không kịp thấy dòng "Waiting for N in-flight requests", nhưng đường đi shutdown đúng như thiết kế và container dừng sau khoảng 1 giây (không bị SIGKILL sau 10 giây).

### Exercise 5.3: Stateless design (`05-scaling-reliability/production/app.py`)

- **Anti-pattern:** giữ lịch sử hội thoại trong biến Python (`conversation_history = {}`). Khi chạy nhiều instance, mỗi instance có RAM riêng nên request thứ 2 rơi vào instance khác sẽ không thấy lịch sử.
- **Cách đúng (đã cài ở production):** mọi state nằm trong Redis. `save_session` ghi `session:{id}` bằng `SETEX` (có TTL 1 giờ), `load_session` đọc lại, `append_to_history` giữ tối đa 20 message gần nhất. Bất kỳ instance nào cũng đọc được cùng một session. App còn có phương án dự phòng (fallback) dùng dict trong RAM nếu không có Redis, nhưng khi đó phản hồi báo `"storage": "in-memory"` (không scale được).
- `/ready` và `/health` kiểm tra `ping` Redis; mỗi instance có `INSTANCE_ID` riêng và trả `served_by` để thấy ai xử lý request.

### Exercise 5.4: Load balancing

Stack: `nginx` (cổng 8080) → 3 bản sao `agent` → `redis`.

```bash
touch .env.local
docker compose -p k5-day14-scaling up -d --build --scale agent=3
docker compose -p k5-day14-scaling ps
# agent-1, agent-2, agent-3: Up (healthy), 8000/tcp
# nginx: 0.0.0.0:8080->80/tcp
# redis: Up (healthy)
```

Nginx (`nginx.conf`) dùng DNS nội bộ của Docker (`resolver 127.0.0.11`): tên `agent` trả về địa chỉ của cả 3 container nên request được chia vòng tròn (round-robin). `proxy_next_upstream error timeout http_503` cho phép tự thử instance khác nếu một instance lỗi. Header `X-Served-By` cho biết instance nào xử lý.

Kết quả khi dừng `agent-1`, gọi `/health` 6 lần: header `X-Served-By` luân phiên giữa hai địa chỉ còn lại (`172.19.0.4` và `172.19.0.5`), không có request nào lỗi. Endpoint của stack này là `POST /chat` (không có `/ask`).

### Exercise 5.5: Test stateless

`python test_stateless.py` (chạy với `-X utf8` vì console Windows mặc định không in được tiếng Việt):

```text
Session ID: e4585dbd-4efb-4c1d-a787-567ffc702f1a
Request 1: [instance-3a9293]
Request 2: [instance-41d368]
Request 3: [instance-419ffe]
Request 4: [instance-3a9293]
Request 5: [instance-41d368]
Instances used: {'instance-3a9293', 'instance-41d368', 'instance-419ffe'}
✅ All requests served despite different instances!
Total messages: 10
✅ Session history preserved across all instances via Redis!
```

Thử thêm tự làm: dừng một instance (`docker stop k5-day14-scaling-agent-1`), rồi:
- Đọc lại `GET /chat/<session>/history` → vẫn đủ **10 message**.
- Gửi tiếp 6 request cùng `session_id` → cả 6 đều **200**, và history tăng tới mức trần 20 message (giữ 20 message gần nhất).

Kết luận: mất một instance không làm mất hội thoại vì state nằm ở Redis, không nằm trong instance. Sau khi test đã `docker compose -p k5-day14-scaling down`.

## Part 6: Final Project (`06-lab-complete/`)

### Các file đã hoàn thành (thay TODO trong bản khung)

| File | Làm gì |
|------|--------|
| `app/config.py` | Đọc `PORT`, `ENVIRONMENT`, `AGENT_API_KEY`, `REDIS_URL`, `RATE_LIMIT_PER_MINUTE`, `DAILY_BUDGET_USD`, `MONTHLY_BUDGET_USD` từ biến môi trường, có giá trị mặc định; không có secret trong code |
| `app/redis_client.py` | Client Redis tạo bằng `redis.from_url` (kết nối lazy nên app vẫn khởi động khi Redis chưa sẵn sàng); `redis_healthy()` ping Redis, lỗi → `False` |
| `app/auth.py` | `verify_api_key`: đọc header `X-API-Key`, so với `AGENT_API_KEY` bằng `hmac.compare_digest`; thiếu/sai → 401 |
| `app/rate_limiter.py` | Sliding window trong Redis (sorted set), "dọn cũ → đếm → thêm" chạy trong **một script Lua** nên nguyên tử; vượt giới hạn → 429 kèm `Retry-After`; Redis lỗi → 503 (fail closed) |
| `app/cost_guard.py` | Cộng dồn chi phí vào Redis theo **ngày** (`cost:day:YYYY-MM-DD`) và **tháng** (`cost:month:YYYY-MM`) bằng `INCRBYFLOAT`; vượt `DAILY_BUDGET_USD`/`MONTHLY_BUDGET_USD` → 402 |
| `app/main.py` | `/health` (luôn 200), `/ready` (503 khi Redis lỗi), `POST /ask` (auth → rate limit → budget → LLM → ghi chi phí), log JSON, graceful shutdown qua `lifespan` |
| `Dockerfile` | Multi-stage, `python:3.11-slim`, user non-root, `HEALTHCHECK`, `CMD` dùng `exec uvicorn ... --port ${PORT:-8000}` để uvicorn là PID 1 |
| `docker-compose.yml` | Service `agent` (build) + `redis:7-alpine` có healthcheck, `REDIS_URL=redis://redis:6379/0`, `depends_on: service_healthy`, `env_file` với `required: false` |
| `.dockerignore`, `.env.example` | Loại `.env`, `__pycache__`, `venv`...; liệt kê đủ biến môi trường (không có secret thật) |
| `railway.toml`, `render.yaml` | Cấu hình deploy: builder `DOCKERFILE` + `healthcheckPath = "/health"`; Render dùng `generateValue: true` cho `AGENT_API_KEY` và Key Value làm Redis |

### Kết quả `check_production_ready.py`

> **Lưu ý trung thực về môi trường chạy:** máy này dùng Windows và bản WSL Ubuntu bị hỏng (thiếu file ổ ảo `ext4.vhdx`), nên mình chạy script chấm **bên trong một container Linux** (`python:3.11` + Docker CLI, nối vào Docker daemon của máy, `--network host`). Môi trường này là POSIX (`os.name == "posix"`) nên bài kiểm tra SIGTERM chạy thật. Nếu Lab Coach yêu cầu WSL2, cần chạy lại bằng WSL2 của bạn.

```text
📋 Checklist Deliverable
   ✅ Dockerfile (multi-stage, < 500 MB)
   ✅ docker-compose.yml (agent + redis)
   ✅ .dockerignore
   ✅ Health check endpoint (GET /health)
   ✅ Readiness endpoint (GET /ready)
   ✅ API Key authentication
   ✅ Rate limiting
   ✅ Cost guard
   ✅ Config từ environment variables
   ✅ Structured logging
   ✅ Graceful shutdown
   ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

Một số chi tiết từ lần chạy: image 238 MB (< 500 MB); `429 sau 5 request thành công (RATE_LIMIT_PER_MINUTE=5)`; state rate limit còn sau khi restart agent (nằm trong Redis); `docker stop` thoát với exit code 0 trong 0.8 giây; 12 dòng log đều là JSON hợp lệ.

### Kiểm tra thủ công bằng `docker compose up`

```text
GET /health → {"status":"ok",...}      GET /ready → {"ready":true}
POST /ask không có key → 401
12 lần POST /ask với key đúng → 200 ×10, rồi 429 ×2 (Retry-After: 58)
Redis có 3 khóa: cost:day:2026-11-26, cost:month:2026-11, ratelimit:<hash>
```

### Quyết định thiết kế đáng chú ý

- **Script Lua cho rate limit:** nếu làm `ZCARD` rồi `ZADD` bằng hai lệnh riêng, hai worker chạy đồng thời có thể cùng thấy "còn 1 suất" và cùng lọt qua. Lua chạy nguyên tử trong Redis nên không có race condition.
- **Không lưu API key thô trong Redis:** khóa rate limit dùng 16 ký tự đầu của SHA-256 của key.
- **Fail closed:** nếu Redis chết, `/ask` trả 503 thay vì bỏ qua giới hạn/ngân sách (bảo vệ tiền quan trọng hơn tính sẵn sàng của endpoint này). `/health` vẫn 200 để platform không restart container chỉ vì Redis lỗi.
- **Không tự đăng ký signal handler SIGTERM:** uvicorn đã xử lý (ngừng nhận kết nối mới, chờ request đang chạy xong); tự đăng ký có thể đè mất handler của uvicorn khiến process không thoát.
- **Cost guard toàn cục, không theo user:** chữ ký hàm `check_budget()` / `record_cost(...)` của bản khung không có `user_id`, nên ngân sách tính cho cả hệ thống.

## Part 7: Benchmark & Observability

Toàn bộ số liệu, bảng và phân tích nằm trong [BENCHMARK_REPORT.md](BENCHMARK_REPORT.md). Các thay đổi mã của Part 7:

| File | Thay đổi | Mục đích |
|------|----------|----------|
| `06-lab-complete/benchmark-observability/develop/app.py` | Thêm Histogram `agent_question_length_chars` và `QUESTION_LENGTH.observe(len(body.question))` trong `/ask` | Exercise 7.1: đo phân bố độ dài câu hỏi. Dùng histogram thay vì label để tránh cardinality bùng nổ |
| `.../develop/utils/mock_llm.py` và `.../production/utils/mock_llm.py` | Thêm 2 entry vào `KNOWLEDGE_BASE` (từ khóa `hpa/kubernetes/autoscal` và `jwt`) | Exercise 7.3: sửa 2 câu v2 trả lời sai (`scaling-03`, `security-02`), đạt 100 % không regression |
| `.../production/Dockerfile` | Copy dependencies vào `/app/.local` và `PATH=/app/.local/bin` thay vì `/home/agent/.local` | Sửa lỗi `ModuleNotFoundError: uvicorn`: user `agent` có home là `/app` nên Python tìm user-site ở `/app/.local`, khiến cả 2 container restart liên tục |
| `.github/workflows/eval.yml` (mới) | Job CI chạy eval với `--min-accuracy 0.85` | Exercise 7.3: chặn merge khi chất lượng tụt |

## Nhật ký sử dụng AI (AI log)

Mình dùng Claude Code (một trợ lý AI chạy trong terminal/VS Code) để làm bài này. Phần việc AI làm và phần cần kiểm chứng:

- **AI viết/chạy:** đọc đề và code mẫu, chạy các ví dụ Part 1–5 và ghi kết quả thật vào file này; viết toàn bộ code Part 6 (`app/*.py`, Dockerfile, compose, `.dockerignore`, `.env.example`, `railway.toml`, `render.yaml`); chạy benchmark/eval/Locust/alert và sinh `BENCHMARK_REPORT.md` bằng script đọc trực tiếp từ JSON/CSV.
- **Sai sót đã phát hiện và sửa trong quá trình làm:** (1) lần chạy thí nghiệm alert đầu có lỗi trong script (nhầm `pending` với `firing`, tải nền làm alert cost firing sẵn) nên đã bỏ và chạy lại; (2) `render.yaml` ban đầu thiếu `rootDir` nên sẽ build nhầm Dockerfile ở gốc repo, đã sửa theo tài liệu Render; (3) Dockerfile production của Part 7 có lỗi đường dẫn dependencies, đã sửa.
- **Giới hạn cần biết:** WSL Ubuntu trên máy bị hỏng nên `check_production_ready.py` được chạy trong container Linux (xem Part 6); chưa deploy lên cloud và chưa có ảnh chụp màn hình vì AI không có tài khoản cloud và không có trình duyệt (xem `DEPLOYMENT.md`, `BENCHMARK_REPORT.md` mục 4.1).
- **Mình cần tự kiểm chứng/hiểu:** vì sao dùng Redis cho trạng thái dùng chung (Part 5/6), vì sao Lua script giúp rate limit nguyên tử, vì sao dùng p95/p99 thay cho trung bình, và vì sao `pending` khác `firing`.
