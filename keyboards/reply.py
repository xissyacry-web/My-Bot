from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Каталог"), KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="💳 Пополнить"), KeyboardButton(text="📦 Наличие")],
            [KeyboardButton(text="♻️ Замена"), KeyboardButton(text="🎁 Промокод")],
            [KeyboardButton(text="📜 История"), KeyboardButton(text="🆘 Поддержка")]
        ],
        resize_keyboard=True
    )
