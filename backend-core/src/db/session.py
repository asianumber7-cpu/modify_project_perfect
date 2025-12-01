from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from src.config.settings import settings

# 비동기 엔진 생성
# pool_pre_ping=True: 연결 끊김 시 자동 복구 (Production 필수)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    future=True
)

# 비동기 세션 팩토리
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

class Base(DeclarativeBase):
    """SQLAlchemy 2.0 Style Base Class"""
    pass

async def get_db():
    """Dependency Injection용 DB 세션 제너레이터"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async_session_maker = AsyncSessionLocal