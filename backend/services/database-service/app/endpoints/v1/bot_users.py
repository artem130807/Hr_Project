from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.middleware import get_db
from app.db.v1.models import (
    BotUser, Candidate, Employee, Token, BotUserProgress
)
from app.schemas.v1.bot_users import (
    BotUserRead, BotUserDelete, BotUserCreate, BotUserUpdate, 
    InviteTokenRead, InviteTokenCreate, ReadProgress,
    UpdateProgress
)
from app.schemas.v1.candidates import CandidateRead
from app.db.v1.enums import BotRoles
from app.config import BOT_NAME

router = APIRouter()


@router.get('/users', response_model=list[BotUserRead], status_code=status.HTTP_200_OK)
async def get_all_users_endpoint(role: BotRoles | None = Query(None),
                                 db: AsyncSession = Depends(get_db)):
    """
    Get all users filtered by role
    """
    query = select(BotUser)
    if role:
        query = query.where(BotUser.role == role.value)
    
    result = await db.execute(query)
    return result.scalars().all()


@router.get('/user/{id}', response_model=BotUserRead)
async def get_user_by_id_endpoint(id: int,
                                  db: AsyncSession = Depends(get_db)):
    """
    Get user by id
    """
    user = await db.get(BotUser, id)
    if not user:
        raise HTTPException(404, 'User not found')
    return user


@router.get('/telegram/{telegram_id}/user', response_model=BotUserRead, status_code=status.HTTP_200_OK)
async def get_user_by_tg_id_endpoint(telegram_id: str,
                                     db: AsyncSession = Depends(get_db)):
    """
    Get user by telegram id
    """
    query = select(BotUser).where(BotUser.telegram_id == telegram_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, 'User not found')
    return user


@router.get('/telegram/{telegram_id}/candidate', response_model=CandidateRead, status_code=status.HTTP_200_OK)
async def get_candidate_by_tg_endpoint(telegram_id: str,
                                       db: AsyncSession = Depends(get_db)):
    """
    Get candidate by telegram_id
    """
    query = (select(Candidate)
             .join(BotUser)
             .where(BotUser.telegram_id == telegram_id))
    result = await db.execute(query)
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(404, 'Candidate not found')
    return candidate


@router.post('/user', response_model=BotUserRead, status_code=status.HTTP_201_CREATED)
async def post_user_endpoint(user_data: BotUserCreate,
                             db: AsyncSession = Depends(get_db)):
    """
    Create user 
    """
    user = BotUser()

    user.telegram_id = user_data.telegram_id
    user.name = user_data.name
    user.role = user_data.role

    if user_data.candidate_id:
        candidate = await db.get(Candidate, user_data.candidate_id)
        user.candidate_profile = candidate
    if user_data.employee_id:
        employee = await db.get(Employee, user_data.employee_id)
        user.employee_profile = employee
    
    db.add(user)
    await db.commit()
    await db.refresh(user)

    progress = BotUserProgress(user_id=user.id)
    db.add(progress)
    await db.commit()

    return user


@router.put('/user/{id}', response_model=BotUserRead, status_code=status.HTTP_200_OK)
async def update_user_endpoint(id: int,
                               user_data: BotUserUpdate,
                               db: AsyncSession = Depends(get_db)):
    """
    Patch user by id
    """
    user: BotUser = await db.get(BotUser, id)
    if not user:
        raise HTTPException(404, 'user not found')
    update_data = user_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user

    
@router.delete('/user/{id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_by_id(id: int, 
                            db: AsyncSession = Depends(get_db)):
    user = await db.get(BotUser, id)
    if not user:
        raise HTTPException(404, 'User not found')
    await db.delete(user)
    await db.commit()

    return None


@router.post("/invite_url", status_code=status.HTTP_201_CREATED)
async def post_invite_token_endpoint(data: InviteTokenCreate,
                           db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """
    Role is BotRoles here
    """
    entity_id = str(data.id)
    if data.role == "candidate":
        try:
            cid = int(data.id)
        except (TypeError, ValueError) as exc:
            raise HTTPException(400, "candidate id must be an integer") from exc
        user = await db.get(Candidate, cid)
        entity_id = str(cid)
    elif data.role in ["hr", "art", "owner", "lead"]:
        user = True
    else:
        raise HTTPException(400, f"Unsupported role: {data.role}")
    if user:
        query = select(Token).where(Token.role == data.role).where(Token.entity_id == entity_id)
        result = await db.execute(query)
        token: Token | None = result.scalars().first()
        current_time = datetime.now(timezone.utc)
        if not token or (token.expires_at < current_time):
            token = Token.generate(data.role, entity_id)
            db.add(token)
            await db.commit()
            await db.refresh(token)
        return {"url": f't.me/{BOT_NAME}?start={token.token}'}
    else:
        raise HTTPException(404, "Candidate not found")
    

@router.get('/invite_token/{token}', response_model=InviteTokenRead, status_code=status.HTTP_200_OK)
async def get_invite_token_endpoint(token: str,
                                    db: AsyncSession = Depends(get_db)):
    query = select(Token).where(Token.token == token)
    result = await db.execute(query)
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(404, 'Token not found')
    return token


@router.get("/progress/{user_id}", response_model=ReadProgress, status_code=status.HTTP_200_OK)
async def get_progress(user_id: int, db: AsyncSession = Depends(get_db)):
    query = select(BotUserProgress).where(BotUserProgress.user_id == user_id)
    result = await db.execute(query)
    progress = result.scalar_one_or_none()
    if not progress:
        raise HTTPException(404, "Progress not found")
    return progress


@router.patch('/progress/{telegram_id}', response_model=ReadProgress, status_code=status.HTTP_200_OK)
async def update_progress_by_telegram(
    telegram_id: str, 
    data: UpdateProgress, 
    db: AsyncSession = Depends(get_db)
):
    # Сначала находим пользователя по telegram_id
    user_query = select(BotUser).where(BotUser.telegram_id == telegram_id)
    user_result = await db.execute(user_query)
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(404, "User not found")
    
    # Затем находим прогресс по user_id
    progress_query = select(BotUserProgress).where(BotUserProgress.user_id == user.id)
    progress_result = await db.execute(progress_query)
    progress = progress_result.scalar_one_or_none()
    if not progress:
        raise HTTPException(404, "Progress not found")

    # Обновляем поля
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(progress, field):
            setattr(progress, field, value)

    await db.commit()
    await db.refresh(progress)
    return progress