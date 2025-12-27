from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class User(BaseModel):
    username: str
    full_name: Optional[str] = None
    disabled: Optional[bool] = None

    class Config:
        from_attributes = True  

class UserInDB(User):
    id: int
    hashed_password: str

class UserCreate(BaseModel):
    username: str
    full_name: str
    password: str

class UserRead(User):
    id: int
    username: str

class ProblemSheetBase(BaseModel):
    subject: str = Field(..., max_length=100)
    difficulty: str = Field(..., max_length=50)
    num_problems: int
    additional_info: str | None = None
    file_path: str | None = None

    class Config:
        from_attributes = True  

class ProblemSheetCreate(ProblemSheetBase):
    user_id: int

class ProblemSheetRead(ProblemSheetBase):
    id: int
    created_at: datetime
    user_id: int
    user: UserRead

    class Config:
        from_attributes = True