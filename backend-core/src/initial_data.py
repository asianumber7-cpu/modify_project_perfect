import asyncio
import os
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import AsyncSessionLocal
from src.crud import crud_user
from src.schemas.user import UserCreate

# 환경 변수에서 관리자 정보를 가져오거나 기본값을 사용합니다.
# .env.dev 파일에 정의된 값이 사용됩니다.
SUPERUSER_EMAIL = os.getenv("SUPERUSER_EMAIL", "admin@modify.com")
SUPERUSER_PASSWORD = os.getenv("SUPERUSER_PASSWORD", "super_secure_password1")
SUPERUSER_NAME = os.getenv("SUPERUSER_NAME", "System Admin")

async def init_db(db: AsyncSession) -> None:
    # 1. 관리자 계정 생성 (이미 없으면)
    user = await crud_user.get_user_by_email(db, email=SUPERUSER_EMAIL)
    
    if not user:
        print("Creating initial superuser...")
        user_in = UserCreate(
            email=SUPERUSER_EMAIL,
            password=SUPERUSER_PASSWORD,
            full_name=SUPERUSER_NAME,
            is_superuser=True,
            is_active=True
        )
        # Note: crud_user는 Async 버전을 사용합니다.
        user = await crud_user.create_user(db, user=user_in) 
        print(f"Superuser created: ID={user.id}, Email={user.email}")
    else:
        print("Superuser already exists. Skipping creation.")

async def main() -> None:
    async with AsyncSessionLocal() as session:
        await init_db(session)

if __name__ == "__main__":
    # OS 환경변수 설정이 복잡한 경우를 대비해, asyncio.run으로 실행
    asyncio.run(main())