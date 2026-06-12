from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import PREMIUM_EMOJI, CRYPTO_ASSETS

# Вспомогательные функции для кнопок, чтобы извлекать чистые эмодзи без HTML-тегов
def pb(key: str) -> str:
    if key not in PREMIUM_EMOJI:
        return ""
    return PREMIUM_EMOJI[key][1]  # Берем второй элемент из кортежа (чистый эмодзи)

def pb_coin(asset: str) -> str:
    # Для криптомонет в кнопках возвращаем обычную монетку
    return "🪙"

# ── ГЛАВНОЕ МЕНЮ (inline) ───────────────────────────────────────
def main_menu_inline_kb():
    b = InlineKeyboardBuilder()
    b.button(text=f"{pb('folder')} Каталог",   callback_data="main_catalog")
    b.button(text=f"{pb('user')} Профиль",     callback_data="main_profile")
    b.button(text=f"{pb('hammer')} Замена",    callback_data="main_replace")
    b.button(text=f"{pb('info')} Поддержка",   callback_data="main_support")
    b.button(text=f"{pb('star')} Скидка",      callback_data="main_discount")
    b.adjust(2, 2, 1)
    return b.as_markup()

def back_to_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"{pb('home')} Главное меню", callback_data="back_to_main")
    ]])

# ── КАТАЛОГ ───────────────────────────────────────────────────────────────────
def categories_kb(cats):
    b = InlineKeyboardBuilder()
    for c in cats:
        b.button(text=f"{pb('folder')} {c.name}", callback_data=f"cat_{c.id}")
    b.adjust(2)
    b.row(InlineKeyboardButton(text=f"{pb('home')} Главное меню", callback_data="back_to_main"))
    return b.as_markup()

def products_kb(products):
    b = InlineKeyboardBuilder()
    for p in products:
        qty = "∞" if p.quantity == 0 else str(p.quantity)
        avg = f" ⭐{p.rating_sum/p.rating_count:.1f}" if p.rating_count else ""
        b.button(
            text=f"{pb('box')} {p.name}  {pb('wallet')} {p.price}$  [{qty} шт]{avg}",
            callback_data=f"buy_{p.id}"
        )
    b.adjust(1)
    b.row(InlineKeyboardButton(text=f"{pb('down')} Назад", callback_data="back_to_categories"))
    return b.as_markup()

def product_actions_kb(product_id: int, out_of_stock=False):
    b = InlineKeyboardBuilder()
    if out_of_stock:
        b.button(text=f"{pb('bell')} Уведомить о наличии", callback_data=f"notify_{product_id}")
    else:
        b.button(text=f"{pb('cart')} Купить", callback_data=f"confirm_buy_{product_id}")
    b.button(text=f"{pb('star')} Отзывы", callback_data=f"reviews_{product_id}")
    b.row(InlineKeyboardButton(text=f"{pb('down')} Назад", callback_data="back_to_categories"))
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
    b.button(text=f"{pb('wallet')} Пополнить баланс", callback_data="profile_topup")
    b.button(text=f"{pb('gift')} Промокод",            callback_data="profile_promo")
    b.button(text=f"{pb('books')} История покупок",    callback_data="profile_history")
    b.button(text=f"{pb('link')} Реф. ссылка",         callback_data="profile_ref")
    b.button(text=f"{pb('home')} Главное меню",        callback_data="back_to_main")
    b.adjust(1)
    return b.as_markup()

# ── ОПЛАТА ────────────────────────────────────────────────────────────────────
def crypto_assets_kb():
    b = InlineKeyboardBuilder()
    for asset in CRYPTO_ASSETS:
        coin = pb_coin(asset)
        b.button(text=f"{coin} {asset}", callback_data=f"asset_{asset}")
    b.adjust(3)
    b.row(InlineKeyboardButton(text=f"{pb('ban')} Отмена", callback_data="cancel_topup"))
    return b.as_markup()

def payment_kb(pay_url: str):
    b = InlineKeyboardBuilder()
    b.button(text=f"{pb('wallet')} Оплатить", url=pay_url)
    b.button(text=f"{pb('check')} Проверить оплату", callback_data="check_payment")
    b.adjust(1)
    return b.as_markup()

# ── ИСТОРИЯ ───────────────────────────────────────────────────────────────────
def history_kb(purchases):
    b = InlineKeyboardBuilder()
    for p in purchases:
        b.button(
            text=f"{pb('box')} #{p.id} · {p.purchased_at.strftime('%d.%m %H:%M')} · {p.price:.2f}$",
            callback_data=f"hist_{p.id}"
        )
    b.button(text=f"{pb('down')} Назад", callback_data="profile_back")
    b.adjust(1)
    return b.as_markup()

def purchase_detail_kb(purchase_id: int, can_review: bool):
    b = InlineKeyboardBuilder()
    if can_review:
        b.button(text=f"{pb('star')} Оставить отзыв", callback_data=f"leave_review_{purchase_id}")
    b.button(text=f"{pb('down')} Назад", callback_data="profile_history")
    b.adjust(1)
    return b.as_markup()

# ── ОТЗЫВ ─────────────────────────────────────────────────────────────────────
def review_rating_kb(purchase_id: int):
    b = InlineKeyboardBuilder()
    for i in range(1, 6):
        b.button(text="⭐" * i, callback_data=f"rate_{purchase_id}_{i}")
    b.adjust(5)
    return b.as_markup()

# ── РАЗБАН / ЗАМЕНА ───────────────────────────────────────────────────────────
def unban_confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"{pb('check')} Отправить", callback_data="unban_confirm"),
        InlineKeyboardButton(text=f"{pb('ban')} Отмена",      callback_data="unban_cancel"),
    ]])

def replace_action_kb(req_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"{pb('check')} Одобрить",  callback_data=f"replace_approve_{req_id}"),
        InlineKeyboardButton(text=f"{pb('ban')} Отклонить",   callback_data=f"replace_reject_{req_id}"),
    ]])

def unban_action_kb(req_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"{pb('unlock')} Одобрить", callback_data=f"unban_approve_{req_id}"),
        InlineKeyboardButton(text=f"{pb('ban')} Отклонить",   callback_data=f"unban_reject_{req_id}"),
    ]])

# ── АДМИН ─────────────────────────────────────────────────────────────────────
def admin_main_kb():
    b = InlineKeyboardBuilder()
    rows = [
        ("━━━ 📦 ТОВАРЫ ━━━",               "admin_noop"),
        (f"{pb('plus')} Добавить товар",     "admin_add_product"),
        (f"{pb('box')} Пополнить товар",     "admin_refill_product"),
        (f"{pb('download')} Загрузить TXT",  "admin_bulk_product"),
        (f"{pb('palette')} Описание",        "admin_edit_desc"),
        (f"{pb('wallet')} Цена товара",      "admin_edit_price"),
        (f"{pb('chart')} Массово цены",      "admin_bulk_price"),
        (f"{pb('trash')} Удалить строки",    "admin_delete_lines"),
        (f"{pb('trash')} Удалить товар",     "admin_delete_product"),
        ("━━━ 📁 КАТЕГОРИИ ━━━",             "admin_noop"),
        (f"{pb('folder')} Добавить кат.",    "admin_add_category"),
        (f"{pb('trash')} Удалить кат.",      "admin_delete_category"),
        ("━━━ 👥 ПОЛЬЗОВАТЕЛИ ━━━",          "admin_noop"),
        (f"{pb('search')} Найти",            "user_search"),
        (f"{pb('wallet')} Баланс",           "user_balance"),
        (f"{pb('ban')} Бан / Разбан",        "user_ban"),
        (f"{pb('star')} Кэшбек",             "user_cashback"),
        (f"{pb('crown')} Топ покупателей",   "admin_top_buyers"),
        ("━━━ 📋 ЗАЯВКИ ━━━",               "admin_noop"),
        (f"{pb('hammer')} Замены",           "admin_replaces"),
        (f"{pb('unlock')} Разблокировки",    "admin_unbans"),
        ("━━━ 🎁 ПРОМОКОДЫ ━━━",             "admin_noop"),
        (f"{pb('plus')} Создать промокод",   "promo_add"),
        (f"{pb('trash')} Удалить промокод",  "promo_delete"),
        (f"{pb('books')} Список промокодов", "promo_list"),
        ("━━━ 📢 РАССЫЛКА ━━━",              "admin_noop"),
        (f"{pb('mega')} Новая рассылка",     "admin_broadcast"),
        (f"{pb('clock')} Запланированные",   "admin_scheduled"),
        ("━━━ 📊 АНАЛИТИКА ━━━",             "admin_noop"),
        (f"{pb('chart')} Статистика",        "admin_stats"),
        (f"{pb('books')} Логи покупок",      "admin_view_logs"),
        ("━━━ 🗄 БАЗА ДАННЫХ ━━━",           "admin_noop"),
        (f"{pb('up')} Экспорт БД",           "admin_export"),
        (f"{pb('download')} Импорт БД",      "admin_import"),
    ]
    for label, cb in rows:
        b.button(text=label, callback_data=cb)
    b.adjust(1)
    return b.as_markup()

def admin_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"{pb('down')} Назад в меню", callback_data="admin_back")
    ]])

def admin_promos_kb():
    b = InlineKeyboardBuilder()
    b.button(text=f"{pb('plus')} Создать",  callback_data="promo_add")
    b.button(text=f"{pb('trash')} Удалить", callback_data="promo_delete")
    b.button(text=f"{pb('books')} Список",  callback_data="promo_list")
    b.button(text=f"{pb('down')} Назад",    callback_data="admin_back")
    b.adjust(2)
    return b.as_markup()

def admin_users_kb():
    b = InlineKeyboardBuilder()
    b.button(text=f"{pb('search')} Найти",        callback_data="user_search")
    b.button(text=f"{pb('wallet')} Баланс",        callback_data="user_balance")
    b.button(text=f"{pb('ban')} Бан/Разбан",       callback_data="user_ban")
    b.button(text=f"{pb('star')} Кэшбек",          callback_data="user_cashback")
    b.button(text=f"{pb('down')} Назад",           callback_data="admin_back")
    b.adjust(2)
    return b.as_markup()

def broadcast_timing_kb():
    b = InlineKeyboardBuilder()
    b.button(text=f"{pb('mega')} Отправить сейчас", callback_data="broadcast_now")
    b.button(text=f"{pb('clock')} Запланировать",   callback_data="broadcast_schedule")
    b.button(text=f"{pb('down')} Назад",            callback_data="admin_back")
    b.adjust(2)
    return b.as_markup()
