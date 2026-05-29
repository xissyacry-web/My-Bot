from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def categories_keyboard(categories):
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.button(text=cat.name, callback_data=f"cat_{cat.id}")
    builder.adjust(2)
    return builder.as_markup()

def products_keyboard(products):
    builder = InlineKeyboardBuilder()
    for prod in products:
        builder.button(text=f"{prod.name} - {prod.price}₽", callback_data=f"buy_{prod.id}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_categories"))
    return builder.as_markup()

def payment_keyboard(pay_url):
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Оплатить через Crypto Bot", url=pay_url)
    builder.button(text="🔄 Проверить оплату", callback_data="check_payment")
    return builder.as_markup()
