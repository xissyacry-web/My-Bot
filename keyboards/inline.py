from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import pe, pe_coin, CRYPTO_ASSETS

# ── ГЛАВНОЕ МЕНЮ ─────────────────────────────────────────────────────────────
def main_menu_inline_kb():
    b = InlineKeyboardBuilder()
    b.button(text=f"{pe('folder')} Каталог",   callback_data="main_catalog")
    b.button(text=f"{pe('user')} Профиль",     callback_data="main_profile")
    b.button(text=f"{pe('hammer')} Замена",    callback_data="main_replace")
    b.button(text=f"{pe('info')} Поддержка",   callback_data="main_support")
    b.button(text=f"{pe('star')} Скидка",      callback_data="main_discount")
    b.adjust(2, 2, 1)
    return b.as_markup()

def back_to_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"{pe('home')} Главное меню", callback_data="back_to_main")
    ]])

# ── КАТАЛОГ ───────────────────────────────────────────────────────────────────
def categories_kb(cats):
    b = InlineKeyboardBuilder()
    for c in cats:
        b.button(text=f"{pe('folder')} {c.name}", callback_data=f"cat_{c.id}")
    b.adjust(2)
    b.row(InlineKeyboardButton(text=f"{pe('home')} Главное меню", callback_data="back_to_main"))
    return b.as_markup()

def products_kb(products):
    b = InlineKeyboardBuilder()
    for p in products:
        qty = "∞" if p.quantity == 0 else str(p.quantity)
        avg = f" ⭐{p.rating_sum/p.rating_count:.1f}" if p.rating_count else ""
        b.button(
            text=f"{pe('box')} {p.name}  {pe('wallet')} {p.price}$  [{qty} шт]{avg}",
            callback_data=f"buy_{p.id}"
        )
    b.adjust(1)
    b.row(InlineKeyboardButton(text=f"{pe('down')} Назад", callback_data="back_to_categories"))
    return b.as_markup()

def product_actions_kb(product_id: int, out_of_stock=False):
    b = InlineKeyboardBuilder()
    if out_of_stock:
        b.button(text=f"{pe('bell')} Уведомить о наличии", callback_data=f"notify_{product_id}")
    else:
        b.button(text=f"{pe('cart')} Купить", callback_data=f"confirm_buy_{product_id}")
    b.button(text=f"{pe('star')} Отзывы", callback_data=f"reviews_{product_id}")
    b.row(InlineKeyboardButton(text=f"{pe('down')} Назад", callback_data="back_to_categories"))
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
    b.button(text=f"{pe('wallet')} Пополнить баланс", callback_data="profile_topup")
    b.button(text=f"{pe('gift')} Промокод",            callback_data="profile_promo")
    b.button(text=f"{pe('books')} История покупок",    callback_data="profile_history")
    b.button(text=f"{pe('link')} Реф. ссылка",         callback_data="profile_ref")
    b.button(text=f"{pe('home')} Главное меню",        callback_data="back_to_main")
    b.adjust(1)
    return b.as_markup()

# ── ОПЛАТА ────────────────────────────────────────────────────────────────────
def crypto_assets_kb():
    b = InlineKeyboardBuilder()
    for asset in CRYPTO_ASSETS:
        coin = pe_coin(asset)
        b.button(text=f"{coin} {asset}", callback_data=f"asset_{asset}")
    b.adjust(3)
    b.row(InlineKeyboardButton(text=f"{pe('ban')} Отмена", callback_data="cancel_topup"))
    return b.as_markup()

def payment_kb(pay_url: str):
    b = InlineKeyboardBuilder()
    b.button(text=f"{pe('wallet')} Оплатить", url=pay_url)
    b.button(text=f"{pe('check')} Проверить оплату", callback_data="check_payment")
    b.adjust(1)
    return b.as_markup()

# ── ИСТОРИЯ ───────────────────────────────────────────────────────────────────
def history_kb(purchases):
    b = InlineKeyboardBuilder()
    for p in purchases:
        b.button(
            text=f"{pe('box')} #{p.id} · {p.purchased_at.strftime('%d.%m %H:%M')} · {p.price:.2f}$",
            callback_data=f"hist_{p.id}"
        )
    b.button(text=f"{pe('down')} Назад", callback_data="profile_back")
    b.adjust(1)
    return b.as_markup()

def purchase_detail_kb(purchase_id: int, can_review: bool):
    b = InlineKeyboardBuilder()
    if can_review:
        b.button(text=f"{pe('star')} Оставить отзыв", callback_data=f"leave_review_{purchase_id}")
    b.button(text=f"{pe('down')} Назад", callback_data="profile_history")
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
        InlineKeyboardButton(text=f"{pe('check')} Отправить", callback_data="unban_confirm"),
        InlineKeyboardButton(text=f"{pe('ban')} Отмена",      callback_data="unban_cancel"),
    ]])

def replace_action_kb(req_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"{pe('check')} Одобрить",  callback_data=f"replace_approve_{req_id}"),
        InlineKeyboardButton(text=f"{pe('ban')} Отклонить",   callback_data=f"replace_reject_{req_id}"),
    ]])

def unban_action_kb(req_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"{pe('unlock')} Одобрить", callback_data=f"unban_approve_{req_id}"),
        InlineKeyboardButton(text=f"{pe('ban')} Отклонить",   callback_data=f"unban_reject_{req_id}"),
    ]])

# ── АДМИН ПАНЕЛЬ ──────────────────────────────────────────────────────────────
def admin_main_kb():
    b = InlineKeyboardBuilder()
    rows = [
        ("━━━ 📦 ТОВАРЫ ━━━",               "admin_noop"),
        (f"{pe('plus')} Добавить товар",     "admin_add_product"),
        (f"{pe('box')} Пополнить товар",     "admin_refill_product"),
        (f"{pe('download')} Загрузить TXT",  "admin_bulk_product"),
        (f"{pe('palette')} Описание",        "admin_edit_desc"),
        (f"{pe('wallet')} Цена товара",      "admin_edit_price"),
        (f"{pe('chart')} Массово цены",      "admin_bulk_price"),
        (f"{pe('trash')} Удалить строки",    "admin_delete_lines"),
        (f"{pe('trash')} Удалить товар",     "admin_delete_product"),
        ("━━━ 📁 КАТЕГОРИИ ━━━",             "admin_noop"),
        (f"{pe('folder')} Добавить кат.",    "admin_add_category"),
        (f"{pe('trash')} Удалить кат.",      "admin_delete_category"),
        ("━━━ 👥 ПОЛЬЗОВАТЕЛИ ━━━",          "admin_noop"),
        (f"{pe('search')} Найти",            "user_search"),
        (f"{pe('wallet')} Баланс",           "user_balance"),
        (f"{pe('ban')} Бан / Разбан",        "user_ban"),
        (f"{pe('star')} Кэшбек",             "user_cashback"),
        (f"{pe('crown')} Топ покупателей",   "admin_top_buyers"),
        ("━━━ 📋 ЗАЯВКИ ━━━",               "admin_noop"),
        (f"{pe('hammer')} Замены",           "admin_replaces"),
        (f"{pe('unlock')} Разблокировки",    "admin_unbans"),
        ("━━━ 🎁 ПРОМОКОДЫ ━━━",             "admin_noop"),
        (f"{pe('plus')} Создать промокод",   "promo_add"),
        (f"{pe('trash')} Удалить промокод",  "promo_delete"),
        (f"{pe('books')} Список промокодов", "promo_list"),
        ("━━━ 📢 РАССЫЛКА ━━━",              "admin_noop"),
        (f"{pe('mega')} Новая рассылка",     "admin_broadcast"),
        (f"{pe('clock')} Запланированные",   "admin_scheduled"),
        ("━━━ 📊 АНАЛИТИКА ━━━",             "admin_noop"),
        (f"{pe('chart')} Статистика",        "admin_stats"),
        (f"{pe('books')} Логи покупок",      "admin_view_logs"),
        ("━━━ 🗄 БАЗА ДАННЫХ ━━━",           "admin_noop"),
        (f"{pe('up')} Экспорт БД",           "admin_export"),
        (f"{pe('download')} Импорт БД",      "admin_import"),
    ]
    for label, cb in rows:
        b.button(text=label, callback_data=cb)
    b.adjust(1)
    return b.as_markup()

def admin_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"{pe('down')} Назад в меню", callback_data="admin_back")
    ]])

def admin_promos_kb():
    b = InlineKeyboardBuilder()
    b.button(text=f"{pe('plus')} Создать",  callback_data="promo_add")
    b.button(text=f"{pe('trash')} Удалить", callback_data="promo_delete")
    b.button(text=f"{pe('books')} Список",  callback_data="promo_list")
    b.button(text=f"{pe('down')} Назад",    callback_data="admin_back")
    b.adjust(2)
    return b.as_markup()

def admin_users_kb():
    b = InlineKeyboardBuilder()
    b.button(text=f"{pe('search')} Найти",        callback_data="user_search")
    b.button(text=f"{pe('wallet')} Баланс",        callback_data="user_balance")
    b.button(text=f"{pe('ban')} Бан/Разбан",       callback_data="user_ban")
    b.button(text=f"{pe('star')} Кэшбек",          callback_data="user_cashback")
    b.button(text=f"{pe('down')} Назад",           callback_data="admin_back")
    b.adjust(2)
    return b.as_markup()

def broadcast_timing_kb():
    b = InlineKeyboardBuilder()
    b.button(text=f"{pe('mega')} Отправить сейчас", callback_data="broadcast_now")
    b.button(text=f"{pe('clock')} Запланировать",   callback_data="broadcast_schedule")
    b.button(text=f"{pe('down')} Назад",            callback_data="admin_back")
    b.adjust(2)
    return b.as_markup()
