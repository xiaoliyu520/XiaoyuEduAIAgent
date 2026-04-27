from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.models.database import User
from app.models.schemas import (
    UserCreate, UserLogin, UserResponse, TokenResponse, ResponseBase,
)
from app.api.deps import get_current_user, require_admin
from app.main import limiter

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=TokenResponse)
@limiter.limit("5/minute")
async def register(request: Request, data: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none():
        raise ValueError("用户名已存在")
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise ValueError("邮箱已存在")

    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        role="user",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.hashed_password):
        raise ValueError("用户名或密码错误")
    if not user.is_active:
        raise ValueError("用户已被禁用")

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.get("/users", response_model=ResponseBase)
async def list_users(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(select(func.count(User.id)))
    total = total_result.scalar()
    result = await db.execute(
        select(User).order_by(User.id.asc()).offset((page - 1) * page_size).limit(page_size)
    )
    users = result.scalars().all()
    return ResponseBase(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [UserResponse.model_validate(u).model_dump() for u in users],
    })


@router.put("/users/{user_id}/toggle-active", response_model=ResponseBase)
async def toggle_user_active(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("用户不存在")
    if user.role == "admin":
        raise ValueError("不能禁用管理员账号")
    user.is_active = not user.is_active
    await db.commit()
    return ResponseBase(data=UserResponse.model_validate(user).model_dump())


@router.delete("/users/{user_id}", response_model=ResponseBase)
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("用户不存在")
    if user.role == "admin":
        raise ValueError("不能删除管理员账号")
    await db.delete(user)
    await db.commit()
    return ResponseBase(message="用户已删除")
