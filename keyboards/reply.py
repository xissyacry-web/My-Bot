# Reply клавиатура убрана — бот использует inline меню
from aiogram.types import ReplyKeyboardRemove

def remove_keyboard():
    return ReplyKeyboardRemove()
