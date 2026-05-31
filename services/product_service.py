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

async def buy_product(session: AsyncSession, user_id: int, product_id: int, amount: int) -> dict:
    user = await session.get(User, user_id)
    if not user or user.is_banned:
        return {"success": False, "error": "Пользователь не найден или заблокирован"}
    product = await session.get(Product, product_id)
    if not product or not product.is_available:
        return {"success": False, "error": "Товар недоступен"}
    if product.quantity > 0 and product.quantity < amount:
        return {"success": False, "error": f"Недостаточно товара. Доступно: {product.quantity} шт."}
    total_price = product.price * amount
    if user.balance < total_price:
        return {"success": False, "error": f"Недостаточно средств. Нужно {total_price:.2f}$, у вас {user.balance:.2f}$"}
    user.balance -= total_price
    if product.quantity > 0:
        product.quantity -= amount
        if product.quantity == 0:
            product.is_available = False
    content_lines = product.content.split('\n') if product.content else []
    selected = content_lines[:amount]
    remaining = content_lines[amount:]
    product.content = '\n'.join(remaining) if remaining else None
    purchase = Purchase(user_id=user_id, product_id=product_id, price=total_price, amount=amount)
    session.add(purchase)
    await session.commit()
    return {
        "success": True,
        "product_name": product.name,
        "file_id": product.file_id,
        "content": '\n'.join(selected),
        "balance": user.balance,
        "quantity_left": product.quantity if product.quantity >= 0 else "∞",
        "price": total_price
    }

async def get_all_products_text(session: AsyncSession) -> str:
    query = select(Product).where(Product.is_available == True).order_by(Product.category_id)
    result = await session.execute(query)
    products = result.scalars().all()
    if not products: return "Товаров нет в наличии"
    cats = {}
    for p in products:
        cat = await session.get(Category, p.category_id)
        cat_name = cat.name if cat else "Без категории"
        if cat_name not in cats: cats[cat_name] = []
        cats[cat_name].append(p)
    text = "➖➖➖ Наличие товаров ➖➖➖\n"
    for cat_name, prods in cats.items():
        text += f"\n📁 {cat_name}:\n"
        for p in prods:
            qty = "∞" if p.quantity == 0 else str(p.quantity)
            text += f"▫️ {p.name}: {qty} шт. (Цена: {p.price}$)\n"
    return text
