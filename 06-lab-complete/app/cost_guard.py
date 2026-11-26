"""
Cost guard (tiêu chí 8) — chặn khi chi phí LLM vượt ngân sách.

  • Cộng dồn chi phí (tính theo token) vào Redis, theo NGÀY và theo THÁNG (UTC)
  • Tổng chi phí vượt DAILY_BUDGET_USD hoặc MONTHLY_BUDGET_USD → HTTP 402
  • Khóa có ngày/tháng trong tên (cost:day:2026-11-26, cost:month:2026-11) nên
    sang kỳ mới tự "reset" mà không cần job dọn dẹp; EXPIRE để Redis tự xóa kỳ cũ.
  • INCRBYFLOAT là nguyên tử → nhiều worker cộng dồn cùng lúc không bị ghi đè.
"""
from datetime import datetime, timezone

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006

DAY_TTL = 2 * 24 * 3600
MONTH_TTL = 35 * 24 * 3600


def _keys() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    return f"cost:day:{now:%Y-%m-%d}", f"cost:month:{now:%Y-%m}"


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    day_key, month_key = _keys()
    try:
        day_cost, month_cost = r.mget(day_key, month_key)
    except Exception:
        raise HTTPException(status_code=503, detail="Cost guard unavailable (Redis down)")

    day_cost = float(day_cost or 0)
    month_cost = float(month_cost or 0)

    if day_cost >= settings.daily_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Daily budget exceeded",
                "used_usd": round(day_cost, 6),
                "budget_usd": settings.daily_budget_usd,
                "resets_at": "00:00 UTC",
            },
        )
    if month_cost >= settings.monthly_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Monthly budget exceeded",
                "used_usd": round(month_cost, 6),
                "budget_usd": settings.monthly_budget_usd,
            },
        )


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    cost = (input_tokens / 1000) * PRICE_INPUT_PER_1K + (output_tokens / 1000) * PRICE_OUTPUT_PER_1K
    day_key, month_key = _keys()
    try:
        pipe = r.pipeline()
        pipe.incrbyfloat(day_key, cost)
        pipe.expire(day_key, DAY_TTL)
        pipe.incrbyfloat(month_key, cost)
        pipe.expire(month_key, MONTH_TTL)
        pipe.execute()
    except Exception:
        # LLM đã được gọi xong, không làm hỏng response chỉ vì ghi sổ thất bại.
        pass
    return cost
