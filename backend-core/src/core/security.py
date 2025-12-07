import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext
from jose import jwt

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.config.settings import settings
from src.models.user import User
from src.schemas.user import UserCreate

# --------------------------------------------------------------------------
# 1. 비밀번호 해싱 및 검증
# --------------------------------------------------------------------------

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """평문 비밀번호와 해시된 비밀번호를 비교합니다."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """새 비밀번호를 해시합니다."""
    return pwd_context.hash(password)

# --------------------------------------------------------------------------
# 2. JWT 토큰 생성 및 관리
# --------------------------------------------------------------------------
def create_access_token(
    user_id: int, expires_delta: Optional[timedelta] = None
) -> str:
    """Access Token을 생성합니다."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
    to_encode = {"exp": expire, "sub": str(user_id), "type": "access"}
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt

def create_refresh_token(
    user_id: int, expires_delta: Optional[timedelta] = None
) -> str:
    """Refresh Token을 생성합니다."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Refresh Token은 Access Token보다 길게 설정 (예: 7일)
        expire = datetime.now(timezone.utc) + timedelta(days=7) 
        
    to_encode = {"exp": expire, "sub": str(user_id), "type": "refresh"}
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt

# --------------------------------------------------------------------------
# 3. 애플리케이션 초기화 (관리자 계정 생성)
# --------------------------------------------------------------------------
async def setup_superuser(db: AsyncSession) -> None:
    """
    환경 변수를 기반으로 초기 관리자 계정을 생성하거나 확인합니다.
    """
    # 순환 참조 방지를 위한 Lazy Import 유지
    from src.crud import crud_user 

    # 1. 관리자 계정 존재 여부 확인
    user = await crud_user.get_user_by_email(db, email=settings.SUPERUSER_EMAIL)
    
    if user:
        # 관리자 계정이 이미 존재함
        if not user.is_superuser:
            # 일반 유저인데 Superuser Email을 사용하는 경우 권한만 업그레이드
            user.is_superuser = True
            db.add(user)
            await db.commit()
            print(f"INFO: User {settings.SUPERUSER_EMAIL} upgraded to superuser.")
        return

    # 2. 관리자 계정 생성
    print("INFO: Creating initial superuser...")
    
    user_in = UserCreate(
        email=settings.SUPERUSER_EMAIL,
        password=settings.SUPERUSER_PASSWORD,
        full_name="System Admin",
        is_superuser=True,
        is_active=True,
    )

    try:
        # crud_user.create_user 내부에서 위에서 정의한 get_password_hash(PBKDF2)를 사용
        await crud_user.create_user(db, user=user_in) 
        print(f"✅ Initial superuser '{settings.SUPERUSER_EMAIL}' created successfully.")
    except Exception as e:
        print(f"❌ ERROR: Failed to create superuser: {e}")
        # 오류 발생 시 애플리케이션 구동이 실패하지 않도록 처리