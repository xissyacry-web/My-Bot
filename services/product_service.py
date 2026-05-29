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
    
    if product.quantity <= 0:
        return {"success": False, "error": "Товар закончился"}

    if user.balance < product.price:
        return {"success": False, "error": f"Недостаточно средств. Ваш баланс: {user.balance:.2f}$"}

    user.balance -= product.price
    product.quantity -= 1
    if product.quantity <= 0:
        product.is_available = False
    
    purchase = Purchase(user_id=user_id, product_id=product_id, price=product.price)
    session.add(purchase)
    await session.commit()
    return {
        "success": True,
        "product_name": product.name,
        "file_id": product.file_id,
        "content": product.content,
        "balance": user.balance,
        "quantity_left": product.quantity
    }

async def get_all_products_text(session: AsyncSession) -> str:
    """Возвращает всё наличие товаров текстом как ты хочешь"""
    query = select(Product).where(Product.is_available == True).order_by(Product.category_id)
    result = await session.execute(query)
    products = result.scalars().all()
    
    if not products:
        return "Товаров нет в наличии"
    
    # Группируем по категориям
    cats = {}
    for p in products:
        cat = await session.get(Category, p.category_id)
        cat_name = cat.name if cat else "Без категории"
        if cat_name not in cats:
            cats[cat_name] = []
        cats[cat_name].append(p)
    
    text = "➖➖➖ Наличие товаров ➖➖➖\n"
    for cat_name, prods in cats.items():
        text += f"\n📁 {cat_name}:\n"
        for p in prods:
            text += f"▫️ {p.name}: {p.quantity} шт. (Цена: {p.price}$)\n"
    
    return text
