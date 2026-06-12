from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import ReplaceRequest, Purchase

async def create_replace_request(session, user_id, log_info, photos=None, complaint=""):
    purchase = (await session.execute(
        select(Purchase).where(Purchase.user_id == user_id, Purchase.status == 'completed')
        .order_by(Purchase.purchased_at.desc()).limit(1)
    )).scalar_one_or_none()
    if not purchase:
        raise ValueError("Нет завершённых покупок")
    req = ReplaceRequest(
        user_id=user_id, purchase_id=purchase.id,
        log_info=log_info, photos=','.join(photos) if photos else None, complaint=complaint
    )
    session.add(req)
    await session.commit()
    return req
