from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import Category, Product, Purchase, User

async def get_categories(session: AsyncSession, parent_id=None):
    return (await session.execute(
        select(Category).where(Category.parent_id == parent_id, Category.is_active == True)
    )).scalars().all()

async def get_products_by_category(session: AsyncSession, category_id: int):
    return (await session.execute(
        select(Product).where(Product.category_id == category_id, Product.is_available == True)
    )).scalars().all()

async def buy_product(session: AsyncSession, user_id: int, product_id: int,
                      amount: int, discount_pct: int = 0) -> dict:
    user = await session.get(User, user_id)
    if not user or user.is_banned:
        return {"success": False, "error": "Пользователь заблокирован"}
    product = await session.get(Product, product_id)
    if not product or not product.is_available:
        return {"success": False, "error": "Товар недоступен"}
    if product.quantity > 0 and product.quantity < amount:
        return {"success": False, "error": f"Доступно только {product.quantity} шт."}

    unit_price = round(product.price * (1 - discount_pct / 100), 2) if discount_pct else product.price
    total_price = round(unit_price * amount, 2)

    if user.balance < total_price:
        return {"success": False, "error": f"Недостаточно средств. Нужно {total_price:.2f}$, у вас {user.balance:.2f}$"}

    # кэшбек
    cashback = round(total_price * user.cashback_pct / 100, 4)

    user.balance -= total_price
    user.balance += cashback
    user.total_spent += total_price

    if product.quantity > 0:
        product.quantity -= amount
        if product.quantity == 0:
            product.is_available = False

    lines = [l for l in (product.content or "").split('\n') if l.strip()]
    selected = lines[:amount]
    product.content = '\n'.join(lines[amount:]) or None

    purchase = Purchase(user_id=user_id, product_id=product_id,
                        price=total_price, amount=amount, cashback=cashback)
    session.add(purchase)
    await session.commit()
    await session.refresh(purchase)

    return {
        "success": True,
        "purchase_id": purchase.id,
        "product_name": product.name,
        "file_id": product.file_id,
        "content": '\n'.join(selected),
        "selected_lines": selected,
        "balance": user.balance,
        "quantity_left": product.quantity,
        "price": unit_price,
        "total_price": total_price,
        "cashback": cashback,
        "cashback_pct": user.cashback_pct,
    }
