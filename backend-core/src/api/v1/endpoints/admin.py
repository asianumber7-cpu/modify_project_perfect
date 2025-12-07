from typing import Any, Literal
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.schemas.email import EmailBroadcastRequest, EmailStatusResponse 
from src.core.celery_app import broadcast_email_task 
from src.api.deps import get_db, get_current_user
from src.schemas.admin import DashboardStatsResponse, SalesData
from src.models.user import User


router = APIRouter()

def check_superuser(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="The user doesn't have enough privileges"
        )
    return current_user


@router.get("/dashboard", response_model=DashboardStatsResponse)
async def get_admin_dashboard_stats(
    time_range: Literal["daily", "weekly", "monthly"] = Query("weekly"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_superuser),
) -> Any:
    """
    관리자 대시보드 통계 조회
    """
    
    # [Mock Data]
    sales_trend = []
    
    if time_range == "weekly":
        sales_trend = [
            {"label": "월", "value": 120}, {"label": "화", "value": 190}, 
            {"label": "수", "value": 300}, {"label": "목", "value": 500}, 
            {"label": "금", "value": 200}, {"label": "토", "value": 300}, 
            {"label": "일", "value": 450}
        ]
    elif time_range == "monthly":
         sales_trend = [
            {"label": "1주", "value": 1500}, {"label": "2주", "value": 2200}, 
            {"label": "3주", "value": 1800}, {"label": "4주", "value": 3100}
        ]
    else: # daily
         sales_trend = [
            {"label": "00시", "value": 5}, {"label": "04시", "value": 15}, 
            {"label": "08시", "value": 40}, {"label": "12시", "value": 80}, 
            {"label": "16시", "value": 60}, {"label": "20시", "value": 110},
        ]
    
    category_data = [
        {"label": "Outer", "value": 35}, 
        {"label": "Top", "value": 40}, 
        {"label": "Bottom", "value": 15}, 
        {"label": "Shoes", "value": 10}
    ]

    return DashboardStatsResponse(
        total_revenue=12450000.0,
        new_orders=45,
        visitors=1230,
        growth_rate=12.5,
        weekly_sales_trend=[SalesData(**d) for d in sales_trend],
        category_sales_pie=[SalesData(**d) for d in category_data]
    )

@router.post("/broadcast-email", response_model=EmailStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_broadcast_email(
    email_req: EmailBroadcastRequest,
    current_user: User = Depends(check_superuser),
) -> Any:
    """
    [비동기] 전체 회원 대상 단체 메일 발송 요청
    - 실제 발송은 Celery Worker가 백그라운드에서 처리합니다.
    """
    # Celery Task 호출 (.delay() 사용)
    task = broadcast_email_task.delay(
        subject=email_req.subject,
        body=email_req.body,
        filter_type=email_req.recipients_filter
    )
    
    return EmailStatusResponse(
        message="Broadcast email functionality has been triggered successfully.",
        task_id=str(task.id)
    )