from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def profile_keyboard():
    """Главное меню профиля с твоими кастомными ТГП-иконками во всю линию"""
    builder = InlineKeyboardBuilder()
    
    builder.row(InlineKeyboardButton(text='💳 Пополнить баланс', callback_data="top_up"))
    builder.row(InlineKeyboardButton(text='🎁 Промокод', callback_data="promo"))
    builder.row(InlineKeyboardButton(text='📜 Мои покупки', callback_data="my_orders"))
    
    return builder.as_markup()

def categories_keyboard(categories):
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.row(InlineKeyboardButton(text=str(cat.name), callback_data=f"cat_{cat.id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад в каталог", callback_data="back_to_categories"))
    return builder.as_markup()

def products_keyboard(products):
    builder = InlineKeyboardBuilder()
    for prod in products:
        status = "🟢" if prod.quantity > 0 or prod.quantity is None else "🔴"
        builder.row(InlineKeyboardButton(text=f"{status} {prod.name} — {prod.price}$", callback_data=f"buy_{prod.id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад к категориям", callback_data="back_to_categories"))
    return builder.as_markup()

def payment_keyboard(pay_url: str):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💳 Ссылка на оплату", url=pay_url))
    builder.row(InlineKeyboardButton(text="🔄 Проверить оплату", callback_data="check_payment"))
    return builder.as_markup()

def history_keyboard(purchases):
    builder = InlineKeyboardBuilder()
    for p in purchases:
        builder.row(InlineKeyboardButton(text=f"Покупка #{p.id}", callback_data=f"hist_{p.id}"))
    builder.row(InlineKeyboardButton(text="◀️ В профиль", callback_data="profile_back"))
    return builder.as_markup()

def unban_confirm_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Отправить", callback_data="unban_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="unban_cancel")
    )
    return builder.as_markup()
