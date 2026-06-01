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
        builder.button(text=f"{prod.name} - {prod.price}$", callback_data=f"buy_{prod.id}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_categories"))
    return builder.as_markup()

def payment_keyboard(pay_url):
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Оплатить через Crypto Bot", url=pay_url)
    builder.button(text="🔄 Проверить оплату", callback_data="check_payment")
    return builder.as_markup()

def admin_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить товар", callback_data="admin_add_product")
    builder.button(text="✏️ Пополнить товар", callback_data="admin_refill_product")
    builder.button(text="➕ Добавить категорию", callback_data="admin_add_category")
    builder.button(text="🗑 Удалить товар", callback_data="admin_delete_product")
    builder.button(text="🗑 Удалить категорию", callback_data="admin_delete_category")
    builder.button(text="🎁 Промокоды", callback_data="admin_promocodes")
    builder.button(text="👥 Пользователи", callback_data="admin_users_menu")
    builder.button(text="🔄 Заявки на замену", callback_data="admin_replaces")
    builder.button(text="📨 Рассылка", callback_data="admin_broadcast")
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.adjust(2)
    return builder.as_markup()

def admin_promocodes_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Создать", callback_data="promo_add")
    builder.button(text="🗑 Удалить", callback_data="promo_delete")
    builder.button(text="📋 Список", callback_data="promo_list")
    builder.button(text="🔙 Назад", callback_data="admin_back")
    builder.adjust(2)
    return builder.as_markup()

def admin_users_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔍 Поиск", callback_data="user_search")
    builder.button(text="💰 Изменить баланс", callback_data="user_balance")
    builder.button(text="🚫 Бан/Разбан", callback_data="user_ban")
    builder.button(text="🔙 Назад", callback_data="admin_back")
    builder.adjust(2)
    return builder.as_markup()
