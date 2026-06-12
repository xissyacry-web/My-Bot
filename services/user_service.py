import random, string
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import User
from config import CASHBACK_DEFAULT

def gen_ref_code(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

async def get_user(session: AsyncSession, user_id: int) -> User | None:
    return (await session.execute(select(User).where(User.user_id == user_id))).scalar_one_or_none()

async def create_user(session: AsyncSession, user_id: int, username: str = None, referred_by: int = None) -> User:
    code = gen_ref_code()
    while (await session.execute(select(User).where(User.ref_code == code))).scalar_one_or_none():
        code = gen_ref_code()
    user = User(user_id=user_id, username=username, ref_code=code,
                referred_by=referred_by, cashback_pct=CASHBACK_DEFAULT)
    session.add(user)
    await session.commit()
    return user
