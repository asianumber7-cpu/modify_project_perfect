from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.api.deps import get_db, get_current_user
from src.models.user import User
from src.schemas.user import UserUpdate, UserResponse

router = APIRouter()

# 내 정보 조회 (새로고침 시 최신 정보 가져오기 위함)
@router.get("/me", response_model=UserResponse)
async def read_user_me(
    current_user: User = Depends(get_current_user),
) -> Any:
    return current_user

# 내 정보 수정 (마케팅 동의 토글용)
@router.patch("/me", response_model=UserResponse)
async def update_user_me(
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    현재 로그인한 사용자의 정보를 수정합니다. (마케팅 동의 포함)
    """
    # 수정할 데이터만 추출 (exclude_unset=True는 보내지 않은 필드는 무시함)
    update_data = user_in.model_dump(exclude_unset=True)
    
    # DB 객체 업데이트
    for field, value in update_data.items():
        setattr(current_user, field, value)

    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    
    return current_user