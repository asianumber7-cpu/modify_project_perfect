#!/bin/bash

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

ENV_FILE=".env.dev"

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Error: $ENV_FILE file not found!${NC}"
    echo "Please copy .env.dev.example to .env.dev and fill in the values."
    exit 1
fi

echo "🔍 Checking environment variables in $ENV_FILE..."

# 필수 변수 목록
REQUIRED_VARS=(
    "POSTGRES_USER"
    "POSTGRES_PASSWORD"
    "JWT_SECRET_KEY"
    "EMBEDDING_DIMENSION"
    "GOOGLE_API_KEY"
)

MISSING=0
for VAR in "${REQUIRED_VARS[@]}"; do
    if ! grep -q "^${VAR}=" "$ENV_FILE" || [ -z "$(grep "^${VAR}=" "$ENV_FILE" | cut -d '=' -f2)" ]; then
        echo -e "${RED}❌ Missing or empty variable: $VAR${NC}"
        MISSING=1
    fi
done

# JWT 길이 검증 (간단 체크)
JWT_KEY=$(grep "^JWT_SECRET_KEY=" "$ENV_FILE" | cut -d '=' -f2)
if [ ${#JWT_KEY} -lt 32 ]; then
    echo -e "${RED}❌ Security Risk: JWT_SECRET_KEY is too short (current: ${#JWT_KEY}, required: 32+)${NC}"
    MISSING=1
fi

if [ $MISSING -eq 1 ]; then
    echo -e "${RED}⚠️  Environment check failed. Please fix .env.dev before starting.${NC}"
    exit 1
else
    echo -e "${GREEN}✅ Environment check passed! Ready to launch.${NC}"
fi