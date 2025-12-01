from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator
import re

# 공통 속성
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False
    phone_number: Optional[str] = None 

# 회원가입/생성 시 필요한 속성
class UserCreate(UserBase):
    password: str

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6 or len(v) > 100:
            raise ValueError('비밀번호는 6자 이상 100자 이하이어야 합니다.')
        
        if not re.match(r"^(?=.*[A-Za-z])(?=.*\d).+$", v):
            raise ValueError('비밀번호는 영문과 숫자를 반드시 포함해야 합니다.')
            
        return v

# 업데이트 시 필요한 속성
class UserUpdate(BaseModel): 
    full_name: Optional[str] = None
    password: Optional[str] = None
    is_marketing_agreed: Optional[bool] = None
    phone_number: Optional[str] = None # ✨ 휴대폰 변경 가능

# DB에서 조회해서 나갈 때 쓰는 속성
class UserResponse(UserBase):
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    provider: str = "email"
    created_at: datetime 
    updated_at: datetime 
    is_marketing_agreed: bool 

    model_config = ConfigDict(from_attributes=True)

# 로그인 시 토큰 응답 스키마
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[int] = None

# 🚨 FIX: 외부 파일에서 'User'라는 이름으로 임포트할 때 오류 방지
# UserResponse를 User라는 이름으로도 사용할 수 있게 별칭 지정
User = UserResponse