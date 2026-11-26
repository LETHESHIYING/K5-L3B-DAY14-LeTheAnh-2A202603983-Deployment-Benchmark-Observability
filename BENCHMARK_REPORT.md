# Benchmark & Observability Report — Day 14

**Họ tên:** Lê Thế Anh (MSSV 2A202603983)
**Ngày chạy:** 2026-11-26
**Môi trường:** Windows 11 Pro, Python 3.12, Docker Desktop (Linux containers). Stack Part 7 giới hạn mỗi agent 0.5 CPU / 256 MB.

> **Bằng chứng:** các số liệu dưới đây lấy từ `reports/*.json`, `benchmark-results/*.csv` và `evidence/*`. Ảnh chụp màn hình nằm trong `screenshots/` (chụp tự động bằng Microsoft Edge chế độ headless, nên ảnh không có thanh địa chỉ).

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Latency bình thường của mock LLM nằm quanh 200 ms; 500 ms cho dư địa gấp 2,5 lần mà người dùng vẫn thấy nhanh. Dùng p95, không dùng trung bình, vì trung bình che mất tail latency |
| Error rate `/ask` | < 2 % | Mock LLM cố ý lỗi ~1 % (`MOCK_ERROR_RATE`), nên 2 % là ngưỡng chấp nhận được và vẫn bắt được sự cố thật |
| Accuracy trên golden dataset | ≥ 85 % | Cùng ngưỡng với job CI `.github/workflows/eval.yml`; thấp hơn thì chặn merge |

Ngưỡng alert lỏng hơn SLO một chút (p95 > 1 s, error > 5 %) để tránh báo động giả vì spike ngắn.

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

Mỗi lần chạy: 300 request vào agent v2 (một process), file `reports/load_v2_c<N>.json`.

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.6 | 193.8 | 237.4 | 1679.0 | 0.67% | PASS |
| 10 | 35.5 | 195.2 | 463.1 | 1721.3 | 0.33% | PASS |
| 50 | 94.33 | 220.0 | 597.7 | 1750.3 | 1.00% | FAIL |
| 100 | 44.22 | 744.9 | 3996.8 | 4500.1 | 1.67% | FAIL |

**Nhận xét:** RPS **không tăng tuyến tính** theo concurrency. Từ 1 lên 10 luồng, RPS tăng gấp ~7,7 lần (gần tuyến tính, vì mỗi request chủ yếu *chờ* LLM nên chạy song song được). Lên 50 thì còn tăng nhưng p95 đã vượt SLO (> 500 ms) vì request bắt đầu xếp hàng. Ở 100 luồng RPS **giảm** (còn khoảng một nửa so với 50) và p50 tăng vọt: agent chỉ chạy một process nên bị quá tải, request chờ lâu trong hàng đợi (latency trung bình tăng gấp nhiều lần). Kết luận: có một điểm bão hòa; muốn chịu nhiều tải hơn phải scale ngang (xem mục 5). Lưu ý mẫu 300 request ở c=100 khá nhỏ nên số liệu dao động giữa các lần chạy.

### 2.2 Tail latency (600 request, concurrency 20)

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 205.5 | 242.0 | 502.4 |
| 0.03 (mặc định) | 267.5 | 521.1 | 1714.5 |
| 0.1 | 365.3 | 1694.1 | 1733.0 |

**Nhận xét:** từ 0 lên 0,1 thì **avg chỉ tăng ~1,8 lần, còn p95 tăng ~7 lần** (242 → 1694 ms) và p99 tăng ~3,5 lần. Percentile cao nhạy nhất với request chậm vì chúng phản ánh đúng những người dùng gặp xui. SLO không nên đặt theo average vì 10 % request mất > 1,5 giây vẫn cho trung bình ~365 ms, nhìn "ổn" trong khi 1 trong 10 người phải chờ gần 2 giây.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

Golden dataset 23 câu. Quality gate mặc định: accuracy ≥ 80 % và không regression so với baseline.

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% | 91.3% | 100.0% |
| Avg tokens / câu | 57.7 | 109.1 | 113.7 |
| Tổng cost (USD) | 0.000413 | 0.000762 | 0.000790 |
| Cost / câu đúng (USD) | 0.00041295 | 0.00003627 | 0.00003436 |
| Quality gate | FAIL (accuracy < 80 %) | PASS (so với baseline v1) | PASS (`--min-accuracy 1.0`, so với baseline v2) |

**Những câu v2 trả lời sai ban đầu và cách đã sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm vào `KNOWLEDGE_BASE` (file `utils/mock_llm.py`) một tài liệu kích hoạt bởi từ khóa `jwt`, nói rõ JWT là token có chữ ký số, có thời điểm hết hạn |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm tài liệu kích hoạt bởi `hpa` / `kubernetes` / `autoscal`: HPA scale pod theo CPU, memory hoặc custom metrics |

Từ khóa kích hoạt `jwt` và `hpa` chỉ xuất hiện trong đúng hai câu này của golden dataset nên không làm đổi kết quả câu khác: **0 regression** (`reports/eval_v2_fixed.json`). Chạy v1 so với baseline v2 cho kết quả **exit code 1** (22 câu regression), đúng như mong đợi của một quality gate; job CI tương ứng ở `.github/workflows/eval.yml`.

**Trade-off v1 / v2:** v2 dùng nhiều token hơn (~2×, vì prompt chứa thêm tài liệu retrieval) nên tổng cost cao hơn, và có thêm bước retrieval nên chậm hơn một chút. Nhưng accuracy tăng từ 4,3 % lên 91,3 % (rồi 100 %), nên **cost trên mỗi câu đúng rẻ hơn khoảng 11–12 lần** (0,000413 → 0,0000363 → 0,0000344 USD). Đổi lại một chút latency và chi phí để lấy chất lượng là hợp lý. Latency p95 của lần eval v2 đầu (1574 ms) cao là do một vài request "chậm bất thường" ngẫu nhiên của mock, không phải do sửa KB (lần eval sau p95 chỉ 234 ms).

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải: [screenshots/grafana-dashboard.png](screenshots/grafana-dashboard.png). Chụp lúc đang chạy thí nghiệm A (`MOCK_ERROR_RATE=0.2`) với 8 người dùng ảo: panel *Error rate* đỏ (23,39 %), biểu đồ *Requests/s theo status code* có đường 503, *Instances up* = 2
- [x] Một trace chậm trong Jaeger: [screenshots/jaeger-slow-trace.png](screenshots/jaeger-slow-trace.png), trace `aa3123169769994f14728f924c70a1af`, 1,7 s, span `chat mock-llm-small` chiếm gần hết thời gian
- [x] Một trace lỗi trong Jaeger: [screenshots/jaeger-error-trace.png](screenshots/jaeger-error-trace.png), trace `f1282f5719f09ed1d4ba9d3ac157ac2d`, `POST /ask` trả 503, các span lỗi có biểu tượng đỏ (event `exception` xem trong `evidence/jaeger_error_trace.json`)
- [x] Trang Alerts của Prometheus có alert **firing**: [screenshots/prometheus-alert-firing.png](screenshots/prometheus-alert-firing.png), `AgentHighErrorRate` ở trạng thái FIRING (lần chạy lại thí nghiệm A để chụp: firing sau 94 s, khớp 97 s ở bảng 4.2)

Dữ liệu thô tương ứng: `evidence/alerts_A.json` … `alerts_E.json`, `evidence/jaeger_*`.

### 4.2 Thí nghiệm "phá hệ thống"

Cách đo: tải nền 8 người dùng ảo (Locust) ổn định, 2 agent. Trước khi bắt đầu không alert nào pending/firing. Thời gian tính **từ lúc chạy lệnh đổi cấu hình** (tính cả ~3 giây khởi động lại container; riêng D là từ lúc `docker pause`). Alert phải qua `pending` rồi mới `firing` sau khoảng `for` trong `alert_rules.yml`.

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Metric phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | pending sau 37 s, **firing sau 97 s** (rule `for: 1m`) | `http_requests_total{status=~"5.."}` / tổng `/ask` (> 5 %) |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | pending sau 19 s, **firing sau 140 s** (rule `for: 2m`) | `histogram_quantile(0.95, http_request_duration_seconds_bucket)` (> 1 s) |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | pending sau 71 s, **firing sau 192 s** (rule `for: 2m`, cửa sổ 5 phút) | `rate(llm_cost_usd_total[5m]) * 3600` (> $2/giờ) |
| D | `docker pause` 1 instance | `AgentInstanceDown` | pending sau 12 s, **firing sau 45 s** (rule `for: 30s`) | `up{job="agent"} == 0` |
| E | `AGENT_VERSION=v1` | **Không alert nào** (kiểm tra sau 150 s) | không firing | (không có metric hạ tầng nào đỏ) |

Cột cuối là metric trong câu PromQL của alert, mình chưa chụp panel Grafana tương ứng.

Lưu ý về độ tin cậy: lần chạy đầu của mình dùng 30 người dùng ảo và có lỗi trong script (nhầm trạng thái `pending` thành `firing`, đồng thời 30 người dùng làm `LLMCostBurnRateHigh` firing ngay từ baseline). Kết quả lần đó **đã bỏ**; bảng trên là lần chạy lại sau khi sửa script (khớp chính xác tên alert) và giảm tải xuống 8 người dùng.

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Metric hạ tầng (latency, error rate, instance up) chỉ cho biết agent *chạy được*, không cho biết nó *trả lời đúng*. Phải đo chất lượng riêng: (1) chạy **eval trên golden dataset** định kỳ trên traffic thật hoặc bản canary và đặt alert khi accuracy tụt (đúng cách ở mục 3, v1 so với v2 cho exit code 1 và regression 22 câu); (2) theo dõi **retrieval hit ratio** và độ dài/tokens của câu trả lời, vì v1 làm các chỉ số này đổi hẳn; (3) lấy mẫu câu trả lời cho **LLM-as-judge** hoặc người chấm; (4) thu **phản hồi người dùng** (👍/👎, khiếu nại).

### 4.3 Debug bằng trace

Trace chậm nhất (trong số trace thành công thu được trong lần chạy này, có đủ dòng log tương ứng):

- `trace_id`: `aa3123169769994f14728f924c70a1af`
- Tổng thời gian: **1711 ms**
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (**1687.6 ms, 98.6 %**). Span `agent.retrieve_context` chỉ 18.5 ms (1,1 %). Vậy request chậm vì **LLM upstream chậm, không phải do code của mình**.
- Dòng log tương ứng (grep theo `trace_id`, từ `docker compose logs agent`):

```json
{"ts": "2026-11-26T10:32:03.303486+00:00", "level": "INFO", "service": "observable-agent", "instance": "f694d7b8d73c", "event": "llm_call", "trace_id": "aa3123169769994f14728f924c70a1af", "span_id": "cdb8d4d240a71890", "request_id": "8c47ccc5c5e8", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 72, "output_tokens": 40, "cost_usd": 3.5e-05, "llm_ms": 1686.8}
{"ts": "2026-11-26T10:32:03.304753+00:00", "level": "INFO", "service": "observable-agent", "instance": "f694d7b8d73c", "event": "http_request", "trace_id": "aa3123169769994f14728f924c70a1af", "span_id": "cdb8d4d240a71890", "request_id": "8c47ccc5c5e8", "method": "POST", "route": "/ask", "status": 200, "ms": 1709.6}
```

Trace lỗi (để xem event `exception`): `trace_id` `f1282f5719f09ed1d4ba9d3ac157ac2d`, tổng 856 ms; span `chat mock-llm-small` có `status=ERROR` và event `exception`, cả `agent.run` và `POST /ask` cũng ở trạng thái lỗi. Log tương ứng:

```json
{"ts": "2026-11-26T10:32:00.298646+00:00", "level": "INFO", "service": "observable-agent", "instance": "2b879eb4760a", "event": "llm_error", "trace_id": "f1282f5719f09ed1d4ba9d3ac157ac2d", "span_id": "7d904a14dc2c177f", "request_id": "48bd3b650b8f", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

(Trace lỗi này được tạo bằng cách tạm đặt `MOCK_ERROR_RATE=0.3` rồi trả lại mặc định ngay sau khi lấy dữ liệu.)

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

Số liệu của endpoint `POST /ask` (`benchmark-results/scale_1_stats.csv`, `scale_3_stats.csv`):

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 55.22 | 210 | 1600 | 2300 | 66 / 6598 |
| 3 | 60.18 | 200 | 240 | 1700 | 75 / 7171 |

**Giải thích kết quả:**

- **p95 cải thiện rõ** (1600 → 240 ms). Với 1 instance giới hạn 0,5 CPU, 100 người dùng làm agent bão hòa nên request xếp hàng; thêm instance chia nhỏ hàng đợi.
- **RPS gần như không đổi** (~55 → ~60). Locust là mô hình *vòng kín*: mỗi người dùng ảo chờ 0,5–2 giây giữa hai request (`wait_time`), nên 100 người dùng tối đa chỉ tạo ra khoảng 60–65 request/giây dù server nhanh đến đâu. Muốn thấy RPS tăng phải tăng số người dùng hoặc bỏ thời gian chờ.
- **p99 vẫn ~1,7 s** dù có 3 instance: đó là các request bị LLM "chậm bất thường" (cộng thêm ~1,5 giây), scale ngang không sửa được. **Nút thắt của tail latency nằm ở LLM upstream**, không phải ở số instance.
- **Failures (~1 %)** gần như như nhau (66/6598 và 75/7171): do lỗi giả lập `MOCK_ERROR_RATE=0.01` của LLM, không liên quan đến số instance.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. **Dùng percentile, không dùng trung bình.** Cùng một hệ thống, avg tăng 1,8 lần nhưng p95 tăng 7 lần khi có 10 % request chậm; SLO phải đặt theo p95/p99.
  2. **Metric hạ tầng không đo được chất lượng.** Đổi v2 sang v1 làm accuracy rơi từ 91 % xuống 4 % mà không alert nào kêu; cần eval trên golden dataset + quality gate trong CI.
  3. **Đo đúng cái mình muốn đo.** Lần chạy alert đầu của mình sai vì script nhầm `pending` với `firing` và tải nền làm alert cost firing sẵn; phải kiểm tra baseline sạch trước khi thí nghiệm, và Locust (vòng kín) cho RPS bị giới hạn bởi thời gian chờ chứ không phải sức server.
- Nếu đưa agent này lên production thật, mình sẽ thêm:
  - alert theo **accuracy** của eval chạy định kỳ và theo **retrieval hit ratio**;
  - giám sát ở tầng **Nginx / synthetic check từ bên ngoài**, vì lỗi 504 xảy ra ở load balancer không nằm trong metric của agent;
  - **sampling** cho trace khi lưu lượng lớn, và alert khi `LLMCostBurnRateHigh` kéo dài để chặn chi phí bất ngờ.
