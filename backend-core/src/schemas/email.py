from pydantic import BaseModel, Field
from typing import List, Optional

class EmailBroadcastRequest(BaseModel):
    subject: str = Field(..., min_length=1, description="메일 제목")
    body: str = Field(..., min_length=1, description="메일 본문 (HTML 지원)")
    recipients_filter: Optional[str] = Field("all", description="수신 그룹 (all, active 등)")

class EmailStatusResponse(BaseModel):
    message: str
    task_id: str