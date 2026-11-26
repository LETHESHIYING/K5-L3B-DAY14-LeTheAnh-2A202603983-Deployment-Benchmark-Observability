# ============================================================
# Production Dockerfile — multi-stage, slim, non-root, < 500 MB
#
#   Stage 1 (builder): cài dependencies vào /install
#   Stage 2 (runtime): chỉ copy kết quả cài đặt + mã nguồn, không mang theo
#                      pip cache hay công cụ build
# ============================================================

# ── Stage 1: builder ─────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Copy requirements TRƯỚC code: sửa code không làm mất cache layer cài thư viện
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime ─────────────────────────────────────
FROM python:3.11-slim AS runtime

# User không phải root: nếu app bị khai thác thì kẻ tấn công không có quyền root
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

WORKDIR /app

COPY --from=builder /install /usr/local
COPY app/ ./app/
COPY utils/ ./utils/

RUN chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

EXPOSE 8000

# Docker tự kiểm tra container còn sống không (đọc cổng từ biến PORT)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:%s/health' % os.getenv('PORT','8000'))" || exit 1

# `exec` thay shell bằng uvicorn → uvicorn là PID 1, nhận SIGTERM khi `docker stop`
# ${PORT:-8000}: Railway/Render cấp cổng qua biến PORT
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
