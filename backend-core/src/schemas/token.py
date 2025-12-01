from pydantic import BaseModel
from typing import Union

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int = 3600 # 3600 seconds = 1 hour (FastAPI 표준)

class TokenPayload(BaseModel):
    sub: Union[str, int]
    type: str = "access"