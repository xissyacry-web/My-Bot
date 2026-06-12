from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import pe, pe_coin, CRYPTO_ASSETS

# ── УНИВЕРСАЛЬНАЯ КНОПКА НАЗАД ────────────────────────────────────────────────
def back_btn():
    b = InlineKeyboardBuilder()
    b.button(text="◀️ Назад", callback_data="back_to_menu")
    return b.as_markup()

# ── КАТАЛОГ ───────────────────────────────────────────────────────────────────
def categories_kb(cats):
    b = InlineKeyboardBuilder()
    for c in cats:
        b.button(text=f"📁 {c.name}", callback_data=f"cat_{c.id}")
    b.adjust(2)
    return b.as_markup()

def products_kb(products):
    b = InlineKeyboardBuilder()
    for p in products:
        qty = "∞" if p.quantity == 0 else str(p.quantity)
        avg = f" ⭐{p.rating_sum/p.rating_count:.1f}" if p.rating_count else ""
        b.button(
            text=f"📦 {p.name}  💰{p.price}$  [{qty} шт]{avg}",
            callback_data=f"buy_{p.id}"
        )
    b.adjust(1)
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_categories"))
    return b.as_markup()

def product_actions_kb(product_id: int, out_of_stock=False):
    b = InlineKeyboardBuilder()
    if out_of_stock:
        b.button(text="🔔 Уведомить о наличии", callback_data=f"notify_{product_id}")
    else:
        b.button(text="🛒 Купить", callback_data=f"confirm_buy_{product_id}")
    b.button(text="⭐ Отзывы", callback_data=f"reviews_{product_id}")
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_categories"))
    return b.as_markup()

def amount_kb(product_id: int):
    b = InlineKeyboardBuilder()
    for n in [1, 2, 5, 10]:
        b.button(text=str(n), callback_data=f"quickbuy_{product_id}_{n}")
    b.adjust(4)
    return b.as_markup()

# ── ПРОФИЛЬ ───────────────────────────────────────────────────────────────────
def profile_kb():
    b = InlineKeyboardBuilder()
    b.button(text="💳 Пополнить баланс", callback_data="profile_topup")
    b.button(text="🎁 Промокод",          callback_data="profile_promo")
    b.button(text="📜 История покупок",   callback_data="profile_history")
    b.button(text="🔗 Реф. ссылка",       callback_data="profile_ref")
    b.adjust(1)
    return b.as_markup()

# ── ОПЛАТА ────────────────────────────────────────────────────────────────────
def crypto_assets_kb():
    b = InlineKeyboardBuilder()
    for asset in CRYPTO_ASSETS:
        b.button(text=f"{pe_coin(asset)} {asset}", callback_data=f"asset_{asset}")
    b.adjust(3)
    b.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_topup"))
    return b.as_markup()

def payment_kb(pay_url: str):
    b = InlineKeyboardBuilder()
    b.button(text="💳 Оплатить", url=pay_url)
    b.button(text="🔄 Проверить оплату", callback_data="check_payment")
    b.adjust(1)
    return b.as_markup()

# ── ИСТОРИЯ ───────────────────────────────────────────────────────────────────
def history_kb(purchases):
    b = InlineKeyboardBuilder()
    for p in purchases:
        b.button(
            text=f"📦 #{p.id} · {p.purchased_at.strftime('%d.%m %H:%M')} · {p.price:.2f}$",
            callback_data=f"hist_{p.id}"
        )
    b.button(text="◀️ Назад", callback_data="profile_back")
    b.adjust(1)
    return b.as_markup()

def purchase_detail_kb(purchase_id: int, can_review: bool):
    b = InlineKeyboardBuilder()
    if can_review:
        b.button(text="⭐ Оставить отзыв", callback_data=f"leave_review_{purchase_id}")
    b.button(text="◀️ Назад", callback_data="profile_history")
    b.adjust(1)
    return b.as_markup()

# ── ОТЗЫВ ─────────────────────────────────────────────────────────────────────
def review_rating_kb(purchase_id: int):
    b = InlineKeyboardBuilder()
    for i in range(1, 6):
        b.button(text="⭐" * i, callback_data=f"rate_{purchase_id}_{i}")
    b.adjust(5)
    return b.as_markup()

# ── РАЗБАН ────────────────────────────────────────────────────────────────────
def unban_confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Отправить", callback_data="unban_confirm"),
        InlineKeyboardButton(text="❌ Отмена",    callback_data="unban_cancel"),
    ]])

def replace_action_kb(req_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Одобрить",  callback_data=f"replace_approve_{req_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"replace_reject_{req_id}"),
    ]])

def unban_action_kb(req_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Одобрить",  callback_data=f"unban_approve_{req_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"unban_reject_{req_id}"),
    ]])

# ── АДМИН ГЛАВНОЕ МЕНЮ ────────────────────────────────────────────────────────
def admin_main_kb():
    b = InlineKeyboardBuilder()
    b.button(text="━━━ 📦 ТОВАРЫ ━━━",        callback_data="admin_noop")
    b.button(text="➕ Добавить товар",          callback_data="admin_add_product")
    b.button(text="✏️ Пополнить товар",         callback_data="admin_refill_product")
    b.button(text="🗂 Загрузить TXT",            callback_data="admin_bulk_product")
    b.button(text="📝 Изменить описание",        callback_data="admin_edit_desc")
    b.button(text="💰 Изменить цену",            callback_data="admin_edit_price")
    b.button(text="📊 Массово изменить цены",    callback_data="admin_bulk_price")
    b.button(text="🗑 Удалить строки",           callback_data="admin_delete_lines")
    b.button(text="🗑 Удалить товар",            callback_data="admin_delete_product")
    b.button(text="━━━ 📁 КАТЕГОРИИ ━━━",       callback_data="admin_noop")
    b.button(text="➕ Добавить категорию",        callback_data="admin_add_category")
    b.button(text="🗑 Удалить категорию",        callback_data="admin_delete_category")
    b.button(text="━━━ 👥 ПОЛЬЗОВАТЕЛИ ━━━",    callback_data="admin_noop")
    b.button(text="🔍 Найти пользователя",       callback_data="user_search")
    b.button(text="💰 Изменить баланс",          callback_data="user_balance")
    b.button(text="🚫 Бан / Разбан",             callback_data="user_ban")
    b.button(text="⭐ Изменить кэшбек",          callback_data="user_cashback")
    b.button(text="🏆 Топ покупателей",          callback_data="admin_top_buyers")
    b.button(text="━━━ 📋 ЗАЯВКИ ━━━",          callback_data="admin_noop")
    b.button(text="♻️ Замены",                   callback_data="admin_replaces")
    b.button(text="🔓 Разблокировки",            callback_data="admin_unbans")
    b.button(text="━━━ 🎁 ПРОМОКОДЫ ━━━",       callback_data="admin_noop")
    b.button(text="➕ Создать промокод",          callback_data="promo_add")
    b.button(text="🗑 Удалить промокод",         callback_data="promo_delete")
    b.button(text="📋 Список промокодов",        callback_data="promo_list")
    b.button(text="━━━ 📢 РАССЫЛКА ━━━",        callback_data="admin_noop")
    b.button(text="📨 Новая рассылка",           callback_data="admin_broadcast")
    b.button(text="📅 Запланированные",          callback_data="admin_scheduled")
    b.button(text="━━━ 📊 АНАЛИТИКА ━━━",       callback_data="admin_noop")
    b.button(text="📊 Статистика",               callback_data="admin_stats")
    b.button(text="📜 Логи покупок",             callback_data="admin_view_logs")
    b.button(text="━━━ 🗄 БАЗА ДАННЫХ ━━━",     callback_data="admin_noop")
    b.button(text="📤 Экспорт БД",              callback_data="admin_export")
    b.button(text="📥 Импорт БД",               callback_data="admin_import")
    b.adjust(1)
    return b.as_markup()

def admin_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад в меню", callback_data="admin_back")
    ]])

def admin_promos_kb():
    b = InlineKeyboardBuilder()
    b.button(text="➕ Создать", callback_data="promo_add")
    b.button(text="🗑 Удалить", callback_data="promo_delete")
    b.button(text="📋 Список",  callback_data="promo_list")
    b.button(text="◀️ Назад",   callback_data="admin_back")
    b.adjust(2)
    return b.as_markup()

def admin_users_kb():
    b = InlineKeyboardBuilder()
    b.button(text="🔍 Найти",          callback_data="user_search")
    b.button(text="💰 Баланс",          callback_data="user_balance")
    b.button(text="🚫 Бан/Разбан",      callback_data="user_ban")
    b.button(text="⭐ Кэшбек",          callback_data="user_cashback")
    b.button(text="◀️ Назад",           callback_data="admin_back")
    b.adjust(2)
    return b.as_markup()

def broadcast_timing_kb():
    b = InlineKeyboardBuilder()
    b.button(text="🚀 Отправить сейчас",  callback_data="broadcast_now")
    b.button(text="⏰ Запланировать",      callback_data="broadcast_schedule")
    b.button(text="◀️ Назад",             callback_data="admin_back")
    b.adjust(2)
    return b.as_markup()
