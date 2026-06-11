from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_market_keyboard():
    """Главное меню с кастомными ТГП эмодзи"""
    builder = InlineKeyboardBuilder()
    
    # Пополнить баланс -> 👝 [5276398496008663230]
    # Промокод -> 🎁 [5276422526350681413]
    builder.row(
        InlineKeyboardButton(
            text='<tg-emoji id="5276398496008663230">👝</tg-emoji> Пополнить баланс',
            callback_data="top_up"
        ),
        InlineKeyboardButton(
            text='<tg-emoji id="5276422526350681413">🎁</tg-emoji> Промокод',
            callback_data="promo"
        )
    )
    # Мои покупки -> 🛒 [5278613311858959074]
    builder.row(
        InlineKeyboardButton(
            text='<tg-emoji id="5278613311858959074">🛒</tg-emoji> Мои покупки',
            callback_data="my_orders"
        )
    )
    
    return builder.as_markup()


def get_quantity_keyboard(quantity: int):
    """Клавиатура выбора количества товара с ТГП кнопками плюс/минус"""
    builder = InlineKeyboardBuilder()
    
    # ➖ -> [5244796895443838315]
    # ➕ -> [5242329690135356589]
    # ✅ -> [5278411813468269386]
    builder.row(
        InlineKeyboardButton(
            text='<tg-emoji id="5244796895443838315">➖</tg-emoji>',
            callback_data=f"qty:minus:{quantity}"
        ),
        InlineKeyboardButton(
            text=f'{quantity} шт.',
            callback_data="qty:ignore"
        ),
        InlineKeyboardButton(
            text='<tg-emoji id="5242329690135356589">➕</tg-emoji>',
            callback_data=f"qty:plus:{quantity}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text='<tg-emoji id="5278411813468269386">✅</tg-emoji> Подтвердить и купить',
            callback_data=f"qty:confirm:{quantity}"
        )
    )
    
    return builder.as_markup()


# Создаем псевдоним (alias), чтобы старый импорт в хендлерах не ломался
categories_keyboard = get_market_keyboard
