from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext
from schemas import UserCreate, UserInDB, User
import models
from typing import Optional
from sqlalchemy import select

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def get_user_by_username(db: AsyncSession, username: str) -> Optional[UserInDB]:
    result = await db.execute(select(models.User).where(models.User.username == username))

    user = result.scalars().first()

    if user:
        return UserInDB(
            id=user.id,
            username=user.username,
            full_name=user.full_name,
            hashed_password=user.hashed_password,
            disabled=user.disabled
        )
    return None

async def create_user(db: AsyncSession, user: UserCreate) -> UserInDB:
    hashed_password = pwd_context.hash(str(user.password))
    db_user = models.User(
        username=user.username,
        full_name=user.full_name,
        hashed_password=hashed_password,
        disabled=False
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return UserInDB(
        id=db_user.id,
        username=db_user.username,
        full_name=db_user.full_name,
        hashed_password=db_user.hashed_password,
        disabled=db_user.disabled
    )

async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[UserInDB]:
    user = await get_user_by_username(db, username)
    if not user:
        return None
    if not pwd_context.verify(str(password), user.hashed_password):
        return None
    return user

async def get_all_users(db: AsyncSession) -> list[User]:
    result = await db.execute(models.select(models.User))
    users = result.scalars().all()
    return [User(username=user.username, full_name=user.full_name, disabled=user.disabled) for user in users]