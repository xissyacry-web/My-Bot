from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_market_keyboard():
    # Создаем билдер для удобной сборки кнопок
    builder = InlineKeyboardBuilder()
    
    # Вместо обычного смайлика вставляем тег tg-emoji с нужным ID
    builder.row(
        InlineKeyboardButton(
            text='<tg-emoji id="5431448270311693444">💳</tg-emoji> Пополнить баланс',
            callback_data="top_up"
        ),
        InlineKeyboardButton(
            text='<tg-emoji id="5431448270311693111">🎁</tg-emoji> Промокод',
            callback_data="promo"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text='<tg-emoji id="5431448270311693222">📜</tg-emoji> Мои покупки',
            callback_data="my_orders"
        )
    )
    
    return builder.as_markup()
