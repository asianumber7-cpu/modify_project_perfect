# ---------------------------------------------------
# AI Service Module Dockerfile (Simplified)
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

RUN pip install --upgrade pip setuptools wheel

# [Layer 1] PyTorch (CPU 버전)
RUN pip install --no-cache-dir torch==2.1.2 --index-url https://download.pytorch.org/whl/cpu

# [Layer 2] 무거운 ML 패키지
RUN pip install --no-cache-dir \
    transformers==4.41.2 \
    sentence-transformers==3.0.1 \
    accelerate==0.30.1

# [Layer 3] ultralytics
RUN pip install --no-cache-dir \
    opencv-python-headless==4.9.0.80 \
    ultralytics==8.1.0

# [Layer 4] 나머지 의존성
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt

# ---------------------------------------------------

# 2. Runner Stage
FROM python:3.11.14-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Seoul \
    HF_HOME=/app/models_cache \
    YOLO_VERBOSE=False \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# 런타임 라이브러리
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Builder에서 가상환경 복사
COPY --from=builder /opt/venv /opt/venv

# 유저 설정
RUN addgroup --system appgroup && adduser --system --group appuser
RUN mkdir -p /app/models_cache && chown -R appuser:appgroup /app

# 소스 코드 복사
COPY --chown=appuser:appgroup . .

USER appuser
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
