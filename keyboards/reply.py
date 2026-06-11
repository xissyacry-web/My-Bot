from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

def get_main_reply_keyboard():
    builder = ReplyKeyboardBuilder()
    
    # Вставляем кастомные эмодзи прямо как символы из пака!
    builder.row(
        KeyboardButton(text="📦 Каталог"),
        KeyboardButton(text="👤 Профиль")
    )
    builder.row(
        KeyboardButton(text="♻️ Замена"),
        KeyboardButton(text="🆘 Поддержка"),
        KeyboardButton(text="🏷️ Скидка")
    )
    
    return builder.as_markup(resize_keyboard=True)
