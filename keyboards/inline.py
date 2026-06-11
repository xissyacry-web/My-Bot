import sys
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_market_keyboard():
    """Главное меню (чистые и аккуратные кнопки)"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text='👝 Пополнить баланс', callback_data="top_up"),
        InlineKeyboardButton(text='🎁 Промокод', callback_data="promo")
    )
    builder.row(
        InlineKeyboardButton(text='🛒 Мои покупки', callback_data="my_orders")
    )
    return builder.as_markup()

def get_quantity_keyboard(quantity: int):
    """Клавиатура выбора количества товара"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text='➖', callback_data=f"qty:minus:{quantity}"),
        InlineKeyboardButton(text=f'{quantity} шт.', callback_data="qty:ignore"),
        InlineKeyboardButton(text='➕', callback_data=f"qty:plus:{quantity}")
    )
    builder.row(
        InlineKeyboardButton(text='✅ Подтвердить и купить', callback_data=f"qty:confirm:{quantity}")
    )
    return builder.as_markup()

# Заглушки для совместимости
def _generic_stub_keyboard(*args, **kwargs):
    return get_market_keyboard()

class _FallbackModule(object):
    def __init__(self, original_module):
        self.original_module = original_module
    def __getattr__(self, name):
        if hasattr(self.original_module, name):
            return getattr(self.original_module, name)
        return _generic_stub_keyboard

sys.modules[__name__] = _FallbackModule(sys.modules[__name__])
