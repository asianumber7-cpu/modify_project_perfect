# Backend/backend-core/Dockerfile

# Python 3.11 Slim for lightweight image
FROM python:3.11.7-slim

# C 확장 모듈 빌드 환경 변수
ENV CRYPTOGRAPHY_DONT_BUILD_RUST=1 \
    LDFLAGS="-Wl,--strip-all"

# 환경 변수 설정
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Seoul

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libffi-dev \ 
    libssl-dev \ 
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사 (개발 시 docker-compose에서 volume mount로 오버라이딩됨)
# 🚨 FIX: BUILD 컨텍스트 유지를 위해 src 폴더만 복사하는 것이 더 효율적입니다.
COPY src /app/src

# 실행 포트
EXPOSE 8000
# CMD는 docker-compose에서 uvicorn --reload로 오버라이딩됨