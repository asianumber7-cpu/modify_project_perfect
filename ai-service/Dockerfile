# ---------------------------------------------------
# AI Service Dockerfile (CPU Development Optimized)
# 목표: 빌드 시간 30분 -> 3분 단축
# ---------------------------------------------------

# 1. Base Image
FROM python:3.11.14-slim

# 환경 변수 설정
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # uv가 가상환경을 만들지 않고 시스템에 직접 설치하게 함 (Docker 내에서는 더 효율적)
    UV_SYSTEM_PYTHON=1 \
    # Hugging Face 모델 캐시 경로 (재다운로드 방지)
    HF_HOME=/app/models_cache

WORKDIR /app

# 2. 시스템 패키지 설치
# libgl1-mesa-glx, libglib2.0-0: YOLO(OpenCV) 실행을 위한 필수 의존성입니다.
# curl: 헬스체크 및 유틸리티용
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 3. uv 설치 (세계에서 가장 빠른 Python 패키지 매니저)
# pip 대신 사용하여 의존성 해결 시간을 획기적으로 줄입니다.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 4. PyTorch CPU 버전 우선 설치 (속도 혁신의 핵심)
# GPU(CUDA) 관련 거대 파일(2GB+)을 제외하고 CPU 버전만 받아 빌드 속도를 높입니다.
# 개발 단계에서는 이 설정이 필수적입니다.
RUN uv pip install torch==2.1.2 torchvision --index-url https://download.pytorch.org/whl/cpu

# 5. Requirements 설치
COPY requirements.txt .
# --no-cache를 쓰지 않아도 uv는 빠르고 안전합니다.
RUN uv pip install -r requirements.txt

# 6. 소스 코드 복사
COPY . .

# 7. 실행 명령
# 구조 분석 결과: main.py가 'src' 폴더 안에 있으므로 'src.main:app'이 정확합니다.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]