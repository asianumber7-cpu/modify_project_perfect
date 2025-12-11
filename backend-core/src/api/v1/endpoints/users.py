from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from src.api.deps import get_db, get_current_user
from src.models.user import User
from src.schemas.user import UserUpdate, UserResponse

router = APIRouter()


# =========================================================
# 내 정보 조회
# =========================================================
@router.get("/me", response_model=UserResponse)
async def read_user_me(
    current_user: User = Depends(get_current_user),
) -> Any:
    return current_user


# =========================================================
# 내 정보 수정 (마케팅 동의 토글용)
# =========================================================
@router.patch("/me", response_model=UserResponse)
async def update_user_me(
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """현재 로그인한 사용자의 정보를 수정합니다."""
    update_data = user_in.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(current_user, field, value)

    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    
    return current_user


# =========================================================
# 🆕 [관리자] 회원 목록 조회
# =========================================================
@router.get("/admin/list", response_model=Dict[str, Any])
async def get_users_list(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None, description="이메일 또는 이름 검색"),
    is_active: Optional[bool] = Query(None, description="활성 상태 필터"),
) -> Dict[str, Any]:
    """
    회원 목록 조회 (관리자 전용)
    - 페이지네이션, 검색, 상태 필터 지원
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    
    # 기본 조건
    conditions = []
    
    # 검색어 필터
    if search:
        conditions.append(
            or_(
                User.email.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%")
            )
        )
    
    # 활성 상태 필터
    if is_active is not None:
        conditions.append(User.is_active == is_active)
    
    # 총 개수
    count_stmt = select(func.count(User.id))
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0
    
    # 통계 계산
    # 전체 회원
    all_count_result = await db.execute(select(func.count(User.id)))
    all_count = all_count_result.scalar() or 0
    
    # 활성 회원
    active_stmt = select(func.count(User.id)).where(User.is_active == True)
    active_result = await db.execute(active_stmt)
    active_count = active_result.scalar() or 0
    
    # 마케팅 동의
    marketing_stmt = select(func.count(User.id)).where(User.is_marketing_agreed == True)
    marketing_result = await db.execute(marketing_stmt)
    marketing_count = marketing_result.scalar() or 0
    
    # 관리자
    admin_stmt = select(func.count(User.id)).where(User.is_superuser == True)
    admin_result = await db.execute(admin_stmt)
    admin_count = admin_result.scalar() or 0
    
    # 페이징
    offset = (page - 1) * limit
    stmt = select(User)
    if conditions:
        stmt = stmt.where(*conditions)
    stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)
    
    result = await db.execute(stmt)
    users = result.scalars().all()
    
    return {
        "users": [UserResponse.model_validate(u) for u in users],
        "total": total,
        "page": page,
        "limit": limit,
        "stats": {
            "total": all_count,
            "active": active_count,
            "marketing": marketing_count,
            "admin": admin_count
        }
    }


# =========================================================
# 🆕 [관리자] 회원 상태 변경
# =========================================================
@router.patch("/admin/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: int,
    status_in: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    회원 상태 변경 (관리자 전용)
    - 활성/비활성 전환
    - 관리자 권한 부여/해제
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    
    # 자기 자신은 변경 불가
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="자신의 상태는 변경할 수 없습니다.")
    
    # 대상 사용자 조회
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    target_user = result.scalars().first()
    
    if not target_user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    
    # 상태 업데이트
    if "is_active" in status_in:
        target_user.is_active = status_in["is_active"]
    
    if "is_superuser" in status_in:
        target_user.is_superuser = status_in["is_superuser"]
    
    db.add(target_user)
    await db.commit()
    await db.refresh(target_user)
    
    return target_user


# =========================================================
# 🆕 [관리자] 회원 상세 조회
# =========================================================
@router.get("/admin/{user_id}", response_model=UserResponse)
async def get_user_detail(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """회원 상세 조회 (관리자 전용)"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    
    return user