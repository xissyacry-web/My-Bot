from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_market_keyboard():
    """Главное меню профиля (как на скрине)"""
    builder = InlineKeyboardBuilder()
    
    # Каждая кнопка на отдельной строке во всю ширину
    builder.row(InlineKeyboardButton(text='💳 Пополнить баланс', callback_data="top_up"))
    builder.row(InlineKeyboardButton(text='🎁 Промокод', callback_data="promo"))
    builder.row(InlineKeyboardButton(text='📜 Мои покупки', callback_data="my_orders"))
    
    return builder.as_markup()

def get_quantity_keyboard(quantity: int):
    """Клавиатура выбора количества товара"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text='➖', callback_data=f"qty:minus:{quantity}"),
        InlineKeyboardButton(text=f'{quantity} шт.', callback_data="qty:ignore"),
        InlineKeyboardButton(text='➕', callback_data=f"qty:plus:{quantity}")
    )
    builder.row(
        InlineKeyboardButton(text='✅ Подтвердить и купить', callback_data=f"qty:confirm:{quantity}")
    )
    return builder.as_markup()

# Остальные функции-заглушки, чтобы хендлеры не выдавали ImportError при запуске
def categories_keyboard(categories=None):
    return get_market_keyboard()

def products_keyboard(products=None):
    return get_market_keyboard()

def profile_keyboard():
    return get_market_keyboard()

def history_keyboard(purchases=None):
    return get_market_keyboard()
