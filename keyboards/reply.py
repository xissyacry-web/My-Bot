from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

def main_menu():
    """Главное reply-меню бота"""
    builder = ReplyKeyboardBuilder()
    
    builder.row(
        KeyboardButton(text="📋 Каталог"),
        KeyboardButton(text="👤 Профиль")
    )
    builder.row(
        KeyboardButton(text="♻️ Замена"),
        KeyboardButton(text="🆘 Поддержка"),
        KeyboardButton(text="🏷 Скидка")
    )
    
    return builder.as_markup(resize_keyboard=True)
