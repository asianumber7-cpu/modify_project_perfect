# backend-core/src/schemas/admin.py

from typing import List
from pydantic import BaseModel, Field

# 차트 데이터 모델
class SalesData(BaseModel):
    label: str = Field(..., description="기간 또는 카테고리 이름")
    value: int = Field(..., description="매출액 또는 판매 수량")

# 관리자 대시보드 응답 모델
class DashboardStatsResponse(BaseModel):
    # 주요 KPI (Key Performance Indicators)
    total_revenue: int = Field(..., description="총 매출 (단위: 원)")
    new_orders: int = Field(..., description="신규 주문 건수")
    visitors: int = Field(..., description="총 방문자 수")
    growth_rate: float = Field(..., description="성장률 (%)")
    
    # 차트 데이터
    weekly_sales_trend: List[SalesData] = Field(..., description="기간별 매출 추이 데이터")
    category_sales_pie: List[SalesData] = Field(..., description="카테고리별 판매 데이터")

    class Config:
        from_attributes = True