from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_market_keyboard():
    # Создаем билдер для удобной сборки кнопок
    builder = InlineKeyboardBuilder()
    
    # Вместо обычного смайлика вставляем тег tg-emoji с нужным ID
    builder.row(
        InlineKeyboardButton(
            text='<tg-emoji id="5276398496008663230">👝/tg-emoji> Пополнить баланс',
            callback_data="top_up"
        ),
        InlineKeyboardButton(
            text='<tg-emoji id="5276422526350681413">🎁</tg-emoji> Промокод',
            callback_data="promo"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text='<tg-emoji id="5278613311858959074">🛒</tg-emoji> Мои покупки',
            callback_data="my_orders"
        )
    )
    
    return builder.as_markup()
