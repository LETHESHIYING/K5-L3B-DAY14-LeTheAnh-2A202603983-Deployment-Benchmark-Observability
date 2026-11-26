"""
Rate limiting (tiêu chí 7) — sliding window, state lưu trong Redis.

  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây
  • Vượt giới hạn → HTTP 429 kèm header Retry-After
  • State nằm trong Redis nên mọi worker / instance dùng chung và vẫn còn
    sau khi restart agent.

Mỗi key là một sorted set: member = một request, score = thời điểm (giây).
Toàn bộ "dọn cũ → đếm → thêm mới" chạy trong MỘT script Lua nên nguyên tử:
hai worker gọi đồng thời không thể cùng lọt qua khi chỉ còn 1 suất.
"""
import hashlib
import time
import uuid

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

WINDOW_SECONDS = 60

_SLIDING_WINDOW = """
local key     = KEYS[1]
local now     = tonumber(ARGV[1])
local window  = tonumber(ARGV[2])
local limit   = tonumber(ARGV[3])
local member  = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
local count = redis.call('ZCARD', key)
if count >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry = math.ceil(tonumber(oldest[2]) + window - now)
    if retry < 1 then retry = 1 end
    return {0, retry}
end
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, window + 1)
return {1, limit - count - 1}
"""

_script = r.register_script(_SLIDING_WINDOW)


def check_rate_limit(key: str) -> dict:
    """Raise 429 nếu `key` vượt giới hạn; ngược lại trả thông tin còn lại."""
    limit = settings.rate_limit_per_minute
    # Không lưu API key thô trong Redis, chỉ lưu bản băm.
    digest = hashlib.sha256(key.encode()).hexdigest()[:16]
    try:
        allowed, value = _script(
            keys=[f"ratelimit:{digest}"],
            args=[time.time(), WINDOW_SECONDS, limit, f"{time.time()}:{uuid.uuid4().hex}"],
        )
    except Exception:
        # Không có Redis thì không đếm được → từ chối thay vì bỏ qua giới hạn.
        raise HTTPException(status_code=503, detail="Rate limiter unavailable (Redis down)")

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "limit": limit,
                "window_seconds": WINDOW_SECONDS,
                "retry_after_seconds": int(value),
            },
            headers={
                "Retry-After": str(int(value)),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
            },
        )
    return {"limit": limit, "remaining": int(value)}
