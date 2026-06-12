from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📋 Каталог"),   KeyboardButton(text="👤 Профиль")],
        [KeyboardButton(text="🆘 Поддержка"), KeyboardButton(text="♻️ Замена")],
        [KeyboardButton(text="🏷 Скидка")],
    ], resize_keyboard=True)
