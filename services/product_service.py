from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import Category, Product, Purchase, User

async def get_categories(session: AsyncSession, parent_id: int | None = None):
    query = select(Category).where(Category.parent_id == parent_id, Category.is_active == True)
    result = await session.execute(query)
    return result.scalars().all()

async def get_products_by_category(session: AsyncSession, category_id: int):
    query = select(Product).where(Product.category_id == category_id, Product.is_available == True)
    result = await session.execute(query)
    return result.scalars().all()

async def buy_product(session: AsyncSession, user_id: int, product_id: int) -> dict:
    user = await session.get(User, user_id)
    if not user or user.is_banned:
        return {"success": False, "error": "Пользователь не найден или заблокирован"}

    product = await session.get(Product, product_id)
    if not product or not product.is_available:
        return {"success": False, "error": "Товар недоступен"}

    if user.balance < product.price:
        return {"success": False, "error": f"Недостаточно средств. Ваш баланс: {user.balance:.2f}₽"}

    user.balance -= product.price
    purchase = Purchase(user_id=user_id, product_id=product_id, price=product.price)
    session.add(purchase)
    await session.commit()
    return {
        "success": True,
        "product_name": product.name,
        "file_id": product.file_id,
        "balance": user.balance
    }
