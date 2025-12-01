# ---------------------------------------------------
# AI Service Module Dockerfile
# 위치: ./ai-service/Dockerfile
# ---------------------------------------------------

# 1. Builder Stage
FROM python:3.11.14-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
# pip 업그레이드 및 의존성 설치
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------

# 2. Runner Stage
FROM python:3.11.14-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Seoul \
    HF_HOME=/app/models_cache \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# 런타임 필수 라이브러리 (libgl1 등 최신 데비안 대응)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 가상환경 복사
COPY --from=builder /opt/venv /opt/venv

# 유저 설정
RUN addgroup --system appgroup && adduser --system --group appuser
RUN mkdir -p /app/models_cache && chown -R appuser:appgroup /app

# 소스 코드 복사
COPY . .
RUN chown -R appuser:appgroup /app

USER appuser
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]