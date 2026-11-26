"""
Config — 12-Factor: mọi cấu hình đọc từ biến môi trường.

- Không có secret nào được viết cứng trong code.
- Mỗi giá trị đọc từ env lúc tạo Settings(), có mặc định hợp lý khi chạy local.
- Các biến được liệt kê đầy đủ trong .env.example.
"""
import os
from dataclasses import dataclass, field


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    # Server
    port: int = field(default_factory=lambda: _int("PORT", 8000))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))

    # Security — AGENT_API_KEY rỗng nghĩa là mọi request đều bị từ chối (fail closed)
    agent_api_key: str = field(default_factory=lambda: os.getenv("AGENT_API_KEY", ""))

    # Redis — kết nối lazy, app vẫn khởi động được khi Redis chưa sẵn sàng
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))

    # Rate limit: số request tối đa / 60 giây cho mỗi API key
    rate_limit_per_minute: int = field(default_factory=lambda: _int("RATE_LIMIT_PER_MINUTE", 10))

    # Cost guard (USD): ngân sách theo ngày và theo tháng
    daily_budget_usd: float = field(default_factory=lambda: _float("DAILY_BUDGET_USD", 1.0))
    monthly_budget_usd: float = field(default_factory=lambda: _float("MONTHLY_BUDGET_USD", 10.0))


settings = Settings()
