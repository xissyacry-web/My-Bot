from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import CRYPTO_ASSETS

# Айдишники из твоего config.py, вытащенные напрямую
E_FOLDER = "5278227821364275264"
E_USER = "5275979556308674886"
E_HAMMER = "5276314275994954605"
E_INFO = "5278753302023004775"
E_STAR = "5206476089127372379"
E_HOME = "5278413853577734640"
E_BOX = "5278540791336165644"
E_WALLET = "5276398496008663230"
E_DOWN = "5206510891247371052"
E_BELL = "5206222720416643915"
E_CART = "5278613311858959074"
E_GIFT = "5276422526350681413"
E_BOOKS = "5206626000665868017"
E_LINK = "5278305362703835500"
E_BAN = "5278578973595427038"
E_CHECK = "5278411813468269386"
E_UNLOCK = "5278602437001767574"
E_PLUS = "5242329690135356589"
E_DOWNLOAD = "5276220667182736079"
E_PALETTE = "5276442772826515132"
E_CHART = "5278778882848220741"
E_TRASH = "5276384644739129761"
E_SEARCH = "5276395476646653290"
E_CROWN = "5276229330131772747"
E_MEGA = "5278528159837348960"
E_CLOCK = "5276412364458059956"
E_UP = "5206401524200145033"

# Сводный словарь крипты для кнопок оплаты
CRYPTO_EMOJI_IDS = {
    "TON": "5193179982775476271", "BTC": "5195107400889163662", "ETH": "5194983413773266305",
    "USDT": "5192942020112442148", "LTC": "5193059508942824703", "BNB": "5193004361562745352",
    "TRX": "5195352119535755156", "SOL": "5192685687874280710"
}

# ── ГЛАВНОЕ МЕНЮ (Синие, зеленые и дефолтные кнопки с ТГП) ───────────────────
def main_menu_inline_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Каталог", callback_data="main_catalog", style="primary", icon_custom_emoji_id=E_FOLDER),
            InlineKeyboardButton(text="Профиль", callback_data="main_profile", style="primary", icon_custom_emoji_id=E_USER)
        ],
        [
            InlineKeyboardButton(text="Замена", callback_data="main_replace", style="secondary", icon_custom_emoji_id=E_HAMMER),
            InlineKeyboardButton(text="Поддержка", callback_data="main_support", style="secondary", icon_custom_emoji_id=E_INFO)
        ],
        [
            InlineKeyboardButton(text="Скидка", callback_data="main_discount", style="success", icon_custom_emoji_id=E_STAR)
        ]
    ])

def back_to_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Главное меню", callback_data="back_to_main", style="secondary", icon_custom_emoji_id=E_HOME)
    ]])

# ── КАТАЛОГ ───────────────────────────────────────────────────────────────────
def categories_kb(cats):
    b = InlineKeyboardBuilder()
    for c in cats:
        b.button(text=c.name, callback_data=f"cat_{c.id}", style="primary", icon_custom_emoji_id=E_FOLDER)
    b.adjust(2)
    b.row(InlineKeyboardButton(text="Главное меню", callback_data="back_to_main", style="secondary", icon_custom_emoji_id=E_HOME))
    return b.as_markup()

def products_kb(products):
    b = InlineKeyboardBuilder()
    for p in products:
        qty = "∞" if p.quantity == 0 else str(p.quantity)
        avg = f" ⭐{p.rating_sum/p.rating_count:.1f}" if p.rating_count else ""
        b.button(
            text=f"{p.name} | {p.price}$ [{qty} шт]{avg}",
            callback_data=f"buy_{p.id}",
            style="primary",
            icon_custom_emoji_id=E_BOX
        )
    b.adjust(1)
    b.row(InlineKeyboardButton(text="Назад", callback_data="back_to_categories", style="secondary", icon_custom_emoji_id=E_DOWN))
    return b.as_markup()

def product_actions_kb(product_id: int, out_of_stock=False):
    b = InlineKeyboardBuilder()
    if out_of_stock:
        b.button(text="Уведомить о наличии", callback_data=f"notify_{product_id}", style="primary", icon_custom_emoji_id=E_BELL)
    else:
        b.button(text="Купить", callback_data=f"confirm_buy_{product_id}", style="success", icon_custom_emoji_id=E_CART)
    b.button(text="Отзывы", callback_data=f"reviews_{product_id}", style="secondary", icon_custom_emoji_id=E_STAR)
    b.row(InlineKeyboardButton(text="Назад", callback_data="back_to_categories", style="secondary", icon_custom_emoji_id=E_DOWN))
    return b.as_markup()

def amount_kb(product_id: int):
    b = InlineKeyboardBuilder()
    for n in [1, 2, 5, 10]:
        b.button(text=str(n), callback_data=f"quickbuy_{product_id}_{n}", style="secondary")
    b.adjust(4)
    return b.as_markup()

# ── ПРОФИЛЬ ───────────────────────────────────────────────────────────────────
def profile_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пополнить баланс", callback_data="profile_topup", style="success", icon_custom_emoji_id=E_WALLET)],
        [InlineKeyboardButton(text="Промокод", callback_data="profile_promo", style="primary", icon_custom_emoji_id=E_GIFT)],
        [InlineKeyboardButton(text="История покупок", callback_data="profile_history", style="secondary", icon_custom_emoji_id=E_BOOKS)],
        [InlineKeyboardButton(text="Реф. ссылка", callback_data="profile_ref", style="secondary", icon_custom_emoji_id=E_LINK)],
        [InlineKeyboardButton(text="Главное меню", callback_data="back_to_main", style="secondary", icon_custom_emoji_id=E_HOME)]
    ])

# ── ОПЛАТА ────────────────────────────────────────────────────────────────────
def crypto_assets_kb():
    b = InlineKeyboardBuilder()
    for asset in CRYPTO_ASSETS:
        emoji_id = CRYPTO_EMOJI_IDS.get(asset.upper(), "5192942020112442148")
        b.button(text=asset, callback_data=f"asset_{asset}", style="primary", icon_custom_emoji_id=emoji_id)
    b.adjust(3)
    b.row(InlineKeyboardButton(text="Отмена", callback_data="cancel_topup", style="danger", icon_custom_emoji_id=E_BAN))
    return b.as_markup()

def payment_kb(pay_url: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оплатить", url=pay_url, icon_custom_emoji_id=E_WALLET)],
        [InlineKeyboardButton(text="Проверить оплату", callback_data="check_payment", style="success", icon_custom_emoji_id=E_CHECK)]
    ])

# ── ИСТОРИЯ ───────────────────────────────────────────────────────────────────
def history_kb(purchases):
    b = InlineKeyboardBuilder()
    for p in purchases:
        b.button(
            text=f"#{p.id} · {p.purchased_at.strftime('%d.%m %H:%M')} · {p.price:.2f}$",
            callback_data=f"hist_{p.id}",
            style="secondary",
            icon_custom_emoji_id=E_BOX
        )
    b.button(text="Назад", callback_data="profile_back", style="secondary", icon_custom_emoji_id=E_DOWN)
    b.adjust(1)
    return b.as_markup()

def purchase_detail_kb(purchase_id: int, can_review: bool):
    b = InlineKeyboardBuilder()
    if can_review:
        b.button(text="Оставить отзыв", callback_data=f"leave_review_{purchase_id}", style="success", icon_custom_emoji_id=E_STAR)
    b.button(text="Назад", callback_data="profile_history", style="secondary", icon_custom_emoji_id=E_DOWN)
    b.adjust(1)
    return b.as_markup()

# ── ОТЗЫВ ─────────────────────────────────────────────────────────────────────
def review_rating_kb(purchase_id: int):
    b = InlineKeyboardBuilder()
    for i in range(1, 6):
        b.button(text="⭐" * i, callback_data=f"rate_{purchase_id}_{i}", style="secondary")
    b.adjust(5)
    return b.as_markup()

# ── РАЗБАН / ЗАМЕНА (Красные и зеленые кнопки действий) ────────────────────────
def unban_confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Отправить", callback_data="unban_confirm", style="success", icon_custom_emoji_id=E_CHECK),
        InlineKeyboardButton(text="Отмена", callback_data="unban_cancel", style="danger", icon_custom_emoji_id=E_BAN)
    ]])

def replace_action_kb(req_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Одобрить", callback_data=f"replace_approve_{req_id}", style="success", icon_custom_emoji_id=E_CHECK),
        InlineKeyboardButton(text="Отклонить", callback_data=f"replace_reject_{req_id}", style="danger", icon_custom_emoji_id=E_BAN)
    ]])

def unban_action_kb(req_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Одобрить", callback_data=f"unban_approve_{req_id}", style="success", icon_custom_emoji_id=E_UNLOCK),
        InlineKeyboardButton(text="Отклонить", callback_data=f"unban_reject_{req_id}", style="danger", icon_custom_emoji_id=E_BAN)
    ]])

# ── АДМИН ПАНЕЛЬ ──────────────────────────────────────────────────────────────
def admin_main_kb():
    b = InlineKeyboardBuilder()
    rows = [
        ("━━━ КАТЕГОРИЯ: ТОВАРЫ ━━━", "admin_noop", "secondary", None),
        ("Добавить товар", "admin_add_product", "success", E_PLUS),
        ("Пополнить товар", "admin_refill_product", "primary", E_BOX),
        ("Загрузить TXT", "admin_bulk_product", "primary", E_DOWNLOAD),
        ("Описание", "admin_edit_desc", "secondary", E_PALETTE),
        ("Цена товара", "admin_edit_price", "secondary", E_WALLET),
        ("Массово цены", "admin_bulk_price", "secondary", E_CHART),
        ("Удалить строки", "admin_delete_lines", "danger", E_TRASH),
        ("Удалить товар", "admin_delete_product", "danger", E_TRASH),
        
        ("━━━ КАТЕГОРИЯ: КАТЕГОРИИ ━━━", "admin_noop", "secondary", None),
        ("Добавить кат.", "admin_add_category", "success", E_FOLDER),
        ("Удалить кат.", "admin_delete_category", "danger", E_TRASH),
        
        ("━━━ КАТЕГОРИЯ: ПОЛЬЗОВАТЕЛИ ━━━", "admin_noop", "secondary", None),
        ("Найти", "user_search", "primary", E_SEARCH),
        ("Баланс", "user_balance", "secondary", E_WALLET),
        ("Бан / Разбан", "user_ban", "danger", E_BAN),
        ("Кэшбек", "user_cashback", "secondary", E_STAR),
        ("Топ покупателей", "admin_top_buyers", "success", E_CROWN),
        
        ("━━━ КАТЕГОРИЯ: ЗАЯВКИ ━━━", "admin_noop", "secondary", None),
        ("Замены", "admin_replaces", "primary", E_HAMMER),
        ("Разблокировки", "admin_unbans", "primary", E_UNLOCK),
        
        ("━━━ КАТЕГОРИЯ: ПРОМОКОДЫ ━━━", "admin_noop", "secondary", None),
        ("Создать промокод", "promo_add", "success", E_PLUS),
        ("Удалить промокод", "promo_delete", "danger", E_TRASH),
        ("Список промокодов", "promo_list", "secondary", E_BOOKS),
        
        ("━━━ КАТЕГОРИЯ: РАССЫЛКА ━━━", "admin_noop", "secondary", None),
        ("Новая рассылка", "admin_broadcast", "success", E_MEGA),
        ("Запланированные", "admin_scheduled", "secondary", E_CLOCK),
        
        ("━━━ КАТЕГОРИЯ: АНАЛИТИКА ━━━", "admin_noop", "secondary", None),
        ("Статистика", "admin_stats", "secondary", E_CHART),
        ("Логи покупок", "admin_view_logs", "secondary", E_BOOKS),
        
        ("━━━ КАТЕГОРИЯ: БАЗА ДАННЫХ ━━━", "admin_noop", "secondary", None),
        ("Экспорт БД", "admin_export", "primary", E_UP),
        ("Импорт БД", "admin_import", "primary", E_DOWNLOAD),
    ]
    for label, cb, style, emoji_id in rows:
        b.button(text=label, callback_data=cb, style=style, icon_custom_emoji_id=emoji_id)
    b.adjust(1)
    return b.as_markup()

def admin_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Назад в меню", callback_data="admin_back", style="secondary", icon_custom_emoji_id=E_DOWN)
    ]])

def admin_promos_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Создать", callback_data="promo_add", style="success", icon_custom_emoji_id=E_PLUS),
            InlineKeyboardButton(text="Удалить", callback_data="promo_delete", style="danger", icon_custom_emoji_id=E_TRASH)
        ],
        [
            InlineKeyboardButton(text="Список", callback_data="promo_list", style="secondary", icon_custom_emoji_id=E_BOOKS),
            InlineKeyboardButton(text="Назад", callback_data="admin_back", style="secondary", icon_custom_emoji_id=E_DOWN)
        ]
    ])

def admin_users_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Найти", callback_data="user_search", style="primary", icon_custom_emoji_id=E_SEARCH),
            InlineKeyboardButton(text="Баланс", callback_data="user_balance", style="secondary", icon_custom_emoji_id=E_WALLET)
        ],
        [
            InlineKeyboardButton(text="Бан/Разбан", callback_data="user_ban", style="danger", icon_custom_emoji_id=E_BAN),
            InlineKeyboardButton(text="Кэшбек", callback_data="user_cashback", style="secondary", icon_custom_emoji_id=E_STAR)
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="admin_back", style="secondary", icon_custom_emoji_id=E_DOWN)
        ]
    ])

def broadcast_timing_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Отправить сейчас", callback_data="broadcast_now", style="success", icon_custom_emoji_id=E_MEGA),
            InlineKeyboardButton(text="Запланировать", callback_data="broadcast_schedule", style="secondary", icon_custom_emoji_id=E_CLOCK)
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="admin_back", style="secondary", icon_custom_emoji_id=E_DOWN)
        ]
    ])
