import random, string
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import User
from config import CASHBACK_DEFAULT

def gen_ref_code(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

async def get_or_create_user(session: AsyncSession, user_id: int, username: str = None, ref_code: str = None):
    user = (await session.execute(select(User).where(User.user_id == user_id))).scalar_one_or_none()
    if user:
        # Обновляем username если изменился
        if username and user.username != username:
            user.username = username
            await session.commit()
        return user, False  # (user, is_new)

    # Генерируем уникальный реф-код
    code = gen_ref_code()
    while (await session.execute(select(User).where(User.ref_code == code))).scalar_one_or_none():
        code = gen_ref_code()

    # Ищем реферера
    referred_by = None
    if ref_code:
        referrer = (await session.execute(select(User).where(User.ref_code == ref_code))).scalar_one_or_none()
        if referrer and referrer.user_id != user_id:
            referred_by = referrer.user_id
            referrer.ref_count = (referrer.ref_count or 0) + 1

    user = User(
        user_id=user_id,
        username=username,
        ref_code=code,
        referred_by=referred_by,
        cashback_pct=CASHBACK_DEFAULT,
        balance=0.0,
        total_spent=0.0,
        ref_count=0,
        is_banned=False,
        used_promocodes="",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user, True  # (user, is_new)

async def get_user(session: AsyncSession, user_id: int):
    return (await session.execute(select(User).where(User.user_id == user_id))).scalar_one_or_none()
