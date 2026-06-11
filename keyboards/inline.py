from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import pe

# ── CATALOG ───────────────────────────────────────────────────────────────────

def categories_keyboard(categories):
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.button(text=cat.name, callback_data=f"cat_{cat.id}")
    builder.adjust(2)
    return builder.as_markup()

def products_keyboard(products):
    builder = InlineKeyboardBuilder()
    for prod in products:
        qty = "∞" if prod.quantity == 0 else str(prod.quantity)
        builder.button(
            text=f"{prod.name}  💰{prod.price}$  📦{qty}",
            callback_data=f"buy_{prod.id}"
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_categories"))
    return builder.as_markup()

# ── PROFILE ───────────────────────────────────────────────────────────────────

def profile_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Пополнить баланс", callback_data="profile_topup")
    builder.button(text="🎁 Промокод",          callback_data="profile_promo")
    builder.button(text="📜 Мои покупки",        callback_data="profile_history")
    builder.adjust(1)
    return builder.as_markup()

# ── PAYMENT ───────────────────────────────────────────────────────────────────

def payment_keyboard(pay_url: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Оплатить", url=pay_url)
    builder.button(text="🔄 Проверить", callback_data="check_payment")
    builder.adjust(2)
    return builder.as_markup()

# ── ADMIN MAIN ────────────────────────────────────────────────────────────────

def admin_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить товар",     callback_data="admin_add_product")
    builder.button(text="✏️ Пополнить товар",    callback_data="admin_refill_product")
    builder.button(text="🗂 Загрузить TXT",       callback_data="admin_bulk_product")
    builder.button(text="✏️ Изменить описание",  callback_data="admin_edit_desc")
    builder.button(text="🗑 Удалить строки",      callback_data="admin_delete_lines")
    builder.button(text="➕ Категория",           callback_data="admin_add_category")
    builder.button(text="🗑 Удалить товар",       callback_data="admin_delete_product")
    builder.button(text="🗑 Удалить категорию",  callback_data="admin_delete_category")
    builder.button(text="🎁 Промокоды",           callback_data="admin_promocodes")
    builder.button(text="👥 Пользователи",        callback_data="admin_users_menu")
    builder.button(text="🔄 Замены",              callback_data="admin_replaces")
    builder.button(text="📜 Логи покупок",        callback_data="admin_view_logs")
    builder.button(text="📨 Рассылка",            callback_data="admin_broadcast")
    builder.button(text="📊 Статистика",          callback_data="admin_stats")
    builder.button(text="📤 Экспорт БД",          callback_data="admin_export")
    builder.button(text="📥 Импорт БД",           callback_data="admin_import")
    builder.adjust(2)
    return builder.as_markup()

def admin_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")
    ]])

# ── ADMIN PROMOS ──────────────────────────────────────────────────────────────

def admin_promocodes_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Создать", callback_data="promo_add")
    builder.button(text="🗑 Удалить", callback_data="promo_delete")
    builder.button(text="📋 Список",  callback_data="promo_list")
    builder.button(text="◀️ Назад",   callback_data="admin_back")
    builder.adjust(2)
    return builder.as_markup()

# ── ADMIN USERS ───────────────────────────────────────────────────────────────

def admin_users_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔍 Поиск",           callback_data="user_search")
    builder.button(text="💰 Изменить баланс",  callback_data="user_balance")
    builder.button(text="🚫 Бан/Разбан",       callback_data="user_ban")
    builder.button(text="◀️ Назад",            callback_data="admin_back")
    builder.adjust(2)
    return builder.as_markup()

# ── MISC ──────────────────────────────────────────────────────────────────────

def unban_confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Отправить", callback_data="unban_confirm"),
        InlineKeyboardButton(text="❌ Отмена",    callback_data="unban_cancel"),
    ]])

def history_keyboard(purchases):
    builder = InlineKeyboardBuilder()
    for p in purchases:
        builder.button(
            text=f"#{p.id} — {p.purchased_at.strftime('%d.%m %H:%M')}",
            callback_data=f"hist_{p.id}"
        )
    builder.button(text="◀️ Назад", callback_data="profile_back")
    builder.adjust(1)
    return builder.as_markup()
