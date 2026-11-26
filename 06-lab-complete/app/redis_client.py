"""
Kết nối Redis dùng chung cho rate limiter và cost guard.

- redis.from_url() chỉ tạo client, KHÔNG kết nối ngay, nên app vẫn khởi động được
  khi Redis chưa sẵn sàng (không ping lúc import).
- Timeout ngắn để /ready trả lời nhanh khi Redis chết, thay vì treo.
- redis_healthy() dùng cho GET /ready: Redis không kết nối được → False.
"""
import redis

from app.config import settings

r = redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)


def redis_healthy() -> bool:
    """True nếu PING được Redis, mọi lỗi kết nối → False."""
    try:
        return bool(r.ping())
    except Exception:
        return False
