from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Профиль", callback_data="menu_profile")
    builder.button(text="📁 Каталог", callback_data="menu_catalog")
    builder.button(text="💱 Замена", callback_data="menu_replace")
    # builder.button(text="🔗 Зеркала", callback_data="menu_mirrors")  # если нужно
    builder.adjust(2)
    return builder.as_markup()

def profile_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Пополнить баланс", callback_data="menu_topup")
    builder.button(text="🎁 Активировать купон", callback_data="menu_promo")
    builder.button(text="📜 История покупок", callback_data="menu_history")
    builder.button(text="🔄 История операций", callback_data="menu_operations")
    builder.button(text="⬆️ Назад", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()

def buy_quantity_keyboard(product_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="1 шт", callback_data=f"buy_qty_{product_id}_1")
    builder.button(text="2 шт", callback_data=f"buy_qty_{product_id}_2")
    builder.button(text="5 шт", callback_data=f"buy_qty_{product_id}_5")
    builder.button(text="10 шт", callback_data=f"buy_qty_{product_id}_10")
    builder.button(text="✍️ Ввести вручную", callback_data=f"buy_manual_{product_id}")
    builder.button(text="🔙 Назад", callback_data="back_to_categories")
    builder.adjust(2)
    return builder.as_markup()

# Остальные клавиатуры (categories_keyboard, products_keyboard, payment_keyboard) без изменений
def categories_keyboard(categories):
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.button(text=cat.name, callback_data=f"cat_{cat.id}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="⬆️ Назад", callback_data="back_to_main"))
    return builder.as_markup()

def products_keyboard(products):
    builder = InlineKeyboardBuilder()
    for prod in products:
        builder.button(text=f"{prod.name} - {prod.price}$", callback_data=f"buy_{prod.id}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_categories"))
    return builder.as_markup()

def payment_keyboard(pay_url):
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Оплатить через Crypto Bot", url=pay_url)
    builder.button(text="🔄 Проверить оплату", callback_data="check_payment")
    return builder.as_markup()
