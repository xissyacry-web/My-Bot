from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from config import pe

def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=f"{pe('folder')} Каталог"),   KeyboardButton(text=f"{pe('user')} Профиль")],
        [KeyboardButton(text=f"{pe('info')} Поддержка"),   KeyboardButton(text=f"{pe('hammer')} Замена")],
        [KeyboardButton(text=f"{pe('star')} Скидка")],
    ], resize_keyboard=True)
