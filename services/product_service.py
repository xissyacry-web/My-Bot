from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import User

async def get_user(session: AsyncSession, user_id: int) -> User | None:
    result = await session.execute(select(User).where(User.user_id == user_id))
    return result.scalar_one_or_none()

async def create_user(session: AsyncSession, user_id: int, username: str = None) -> User:
    user = User(user_id=user_id, username=username)
    session.add(user)
    await session.commit()
    return user
