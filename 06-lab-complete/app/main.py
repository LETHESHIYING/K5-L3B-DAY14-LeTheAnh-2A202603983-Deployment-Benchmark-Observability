"""
Production AI Agent — Part 6 Final Project

Chạy:
    uvicorn app.main:app --workers 2

Gồm: /health, /ready, POST /ask (API key + rate limit + cost guard),
log JSON, graceful shutdown.
"""
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


# ──────────────────────────────────────────────────────────
# Structured logging (tiêu chí 10): mỗi dòng log là 1 JSON object
# ──────────────────────────────────────────────────────────
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lvl": record.levelname,
            "event": record.getMessage(),
        }
        # Các trường bổ sung truyền qua logger.info("...", extra={"fields": {...}})
        entry.update(getattr(record, "fields", {}))
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(JsonFormatter())
logger = logging.getLogger("agent")
logger.handlers = [_handler]
logger.setLevel(logging.INFO)
logger.propagate = False  # tránh bị root logger in thêm dòng không phải JSON


def log(event: str, **fields) -> None:
    logger.info(event, extra={"fields": fields})


START_TIME = time.time()
_shutting_down = False


# ──────────────────────────────────────────────────────────
# Graceful shutdown (tiêu chí 11)
#   uvicorn bắt SIGTERM, ngừng nhận kết nối mới, chờ request đang chạy xong rồi
#   chạy phần sau `yield` của lifespan. Không tự đăng ký signal handler để khỏi
#   đè mất handler của uvicorn (nếu đè, process sẽ không bao giờ tắt).
# ──────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    log("startup", environment=settings.environment, port=settings.port)
    yield
    global _shutting_down
    _shutting_down = True
    log("shutdown", detail="graceful shutdown complete")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def access_log(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    log(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        ms=round((time.perf_counter() - start) * 1000, 1),
    )
    return response


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


# ──────────────────────────────────────────────────────────
# Health checks
# ──────────────────────────────────────────────────────────
@app.get("/health")
def health():
    """Liveness: luôn 200 khi process còn chạy, kể cả khi Redis chưa kết nối."""
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "environment": settings.environment,
    }


@app.get("/ready")
def ready():
    """Readiness: 200 khi sẵn sàng, 503 khi Redis không kết nối được hoặc đang shutdown."""
    if _shutting_down or not redis_healthy():
        return JSONResponse(status_code=503, content={"ready": False})
    return {"ready": True}


# ──────────────────────────────────────────────────────────
# Agent endpoint
# ──────────────────────────────────────────────────────────
@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    # Thứ tự: xác thực (Depends) → rate limit → budget → gọi LLM → ghi chi phí
    check_rate_limit(api_key)
    check_budget()

    answer = llm_ask(body.question)

    # Ước lượng token thô: 2 token cho mỗi từ (mock LLM không trả usage thật)
    cost = record_cost(
        input_tokens=len(body.question.split()) * 2,
        output_tokens=len(answer.split()) * 2,
    )
    return {"question": body.question, "answer": answer, "cost_usd": round(cost, 8)}
