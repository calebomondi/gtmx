import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import models
from backend.app.database.connect import get_db
from backend.app.schemas.users import UserCreate, UserResponse
from backend.app.config.settings import settings

router = APIRouter()

@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    user: UserCreate, 
    db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(
        select(models.User).where(models.User.email == str(user.email))
    )
    existing_email = result.scalars().first()

    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Email already exists",
        )

    new_user = models.User(
        id=uuid.uuid4(),
        name=user.name,
        email=str(user.email),
        avatar_url=user.avatar_url,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user

@router.get(
    "/me",
    response_model=UserResponse,
)
async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Auth is faked for now: returns the seeded mock signed-in user."""
    result = await db.execute(
        select(models.User).where(models.User.email == settings.MOCK_USER_EMAIL)
    )
    user = result.scalars().first()
    if user:
        return user

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Mock user not found!",
    )


@router.get(
    "/{user_id}", 
    response_model=UserResponse
)
async def get_user(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(models.User).where(models.User.id == user_id)
    )
    user = result.scalars().first()

    if user:
        return user

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="User Not Found!",
    )