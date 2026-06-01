from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Меню"), KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="💳 Пополнить баланс"), KeyboardButton(text="📦 Наличие товаров")],
            [KeyboardButton(text="♻️ Замена лога"), KeyboardButton(text="🎁 Промокод")],
            [KeyboardButton(text="📜 История покупок"), KeyboardButton(text="🆘 Поддержка")]
        ],
        resize_keyboard=True
    )
