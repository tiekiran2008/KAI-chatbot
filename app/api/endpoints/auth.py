from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.models.user import User
from app.schemas.auth import UserCreate, UserRead, Token

from app.api.deps import get_current_user

router = APIRouter()

@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Retrieve details of the currently authenticated user.
    """
    return current_user
