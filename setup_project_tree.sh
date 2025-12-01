#!/bin/bash

# ==========================================
# MODIFY Project Structure Setup Script
# ==========================================

# 프로젝트 루트 폴더 이름 (현재 폴더가 루트라면 . 으로 설정)
PROJECT_ROOT="."

# __init__.py를 포함한 패키지 폴더 생성 함수
create_package() {
    local dir_path="$PROJECT_ROOT/$1"
    mkdir -p "$dir_path"
    touch "$dir_path/__init__.py"
    echo "📦 Created package: $1"
}

# 단순 폴더 생성 함수
create_dir() {
    local dir_path="$PROJECT_ROOT/$1"
    mkdir -p "$dir_path"
    echo "📂 Created directory: $1"
}

echo "🚀 Initializing MODIFY Project Structure..."

# 1. Backend Core Structure (with __init__.py)
# 상위 폴더부터 순차적으로 생성
create_package "backend-core/src"
create_package "backend-core/src/config"
create_package "backend-core/src/api"
create_package "backend-core/src/api/v1"
create_package "backend-core/src/api/v1/endpoints"
create_package "backend-core/src/core"
create_package "backend-core/src/db"
create_package "backend-core/src/models"
create_package "backend-core/src/schemas"
create_package "backend-core/src/services"
create_package "backend-core/src/middleware" # [New] Middleware 추가
create_package "backend-core/src/utils"
create_package "backend-core/tests"

# 2. AI Service Structure (with __init__.py)
create_package "ai-service/src"
create_package "ai-service/src/core"
create_package "ai-service/src/tasks"
create_package "ai-service/src/models"

# 3. Data & Caches (No init needed)
create_dir "ai-service/models_cache"
create_dir "docker/postgres/init"

# 4. Scripts & Configs
create_dir "scripts"
create_dir "nginx/conf.d"

# 실행 권한 부여
chmod +x "$PROJECT_ROOT/scripts/"*.sh 2>/dev/null || true

echo "✅ All directories and __init__.py files created successfully!"