from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import pe, pe_coin, CRYPTO_ASSETS, PREMIUM_EMOJI

def _btn(text: str, cb: str = None, url: str = None, emoji_key: str = None) -> InlineKeyboardButton:
    """Кнопка с кастомным TG эмодзи иконкой через icon_custom_emoji_id"""
    emoji_id = PREMIUM_EMOJI[emoji_key][0] if emoji_key and emoji_key in PREMIUM_EMOJI else None
    kwargs = dict(text=text)
    if emoji_id:
        kwargs["icon_custom_emoji_id"] = emoji_id
    if cb:
        kwargs["callback_data"] = cb
    if url:
        kwargs["url"] = url
    return InlineKeyboardButton(**kwargs)

# ── ГЛАВНОЕ МЕНЮ ──────────────────────────────────────────────────────────────
def main_menu_inline_kb():
    b = InlineKeyboardBuilder()
    b.add(_btn("Каталог",   cb="main_catalog",  emoji_key="folder"))
    b.add(_btn("Профиль",   cb="main_profile",  emoji_key="user"))
    b.add(_btn("Замена",    cb="main_replace",  emoji_key="hammer"))
    b.add(_btn("Поддержка", cb="main_support",  emoji_key="info"))
    b.add(_btn("Скидка",    cb="main_discount", emoji_key="star"))
    b.adjust(2, 2, 1)
    return b.as_markup()

def back_to_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        _btn("Главное меню", cb="back_to_main", emoji_key="home")
    ]])

# ── КАТАЛОГ ───────────────────────────────────────────────────────────────────
def categories_kb(cats):
    b = InlineKeyboardBuilder()
    for c in cats:
        b.add(_btn(f"{c.name}", cb=f"cat_{c.id}", emoji_key="folder"))
    b.adjust(2)
    b.row(_btn("Главное меню", cb="back_to_main", emoji_key="home"))
    return b.as_markup()

def products_kb(products):
    b = InlineKeyboardBuilder()
    for p in products:
        qty = "∞" if p.quantity == 0 else str(p.quantity)
        avg = f" ⭐{p.rating_sum/p.rating_count:.1f}" if p.rating_count else ""
        b.add(_btn(f"{p.name}  💰{p.price}$  [{qty}]{avg}", cb=f"buy_{p.id}", emoji_key="box"))
    b.adjust(1)
    b.row(_btn("Назад", cb="back_to_categories", emoji_key="down"))
    return b.as_markup()

def product_actions_kb(product_id: int, out_of_stock=False):
    b = InlineKeyboardBuilder()
    if out_of_stock:
        b.add(_btn("Уведомить о наличии", cb=f"notify_{product_id}", emoji_key="bell"))
    else:
        b.add(_btn("Купить", cb=f"confirm_buy_{product_id}", emoji_key="cart"))
    b.add(_btn("Отзывы", cb=f"reviews_{product_id}", emoji_key="star"))
    b.row(_btn("Назад", cb="back_to_categories", emoji_key="down"))
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
    b.add(_btn("Пополнить баланс", cb="profile_topup",   emoji_key="wallet"))
    b.add(_btn("Промокод",          cb="profile_promo",   emoji_key="gift"))
    b.add(_btn("История покупок",   cb="profile_history", emoji_key="books"))
    b.add(_btn("Реф. ссылка",       cb="profile_ref",     emoji_key="link"))
    b.add(_btn("Главное меню",      cb="back_to_main",    emoji_key="home"))
    b.adjust(1)
    return b.as_markup()

# ── ОПЛАТА ────────────────────────────────────────────────────────────────────
def crypto_assets_kb():
    b = InlineKeyboardBuilder()
    asset_icons = {"USDT":"💵","TON":"💎","BTC":"🟡","ETH":"🔷","LTC":"⚪","BNB":"🟠","TRX":"🔴"}
    for asset in CRYPTO_ASSETS:
        icon = asset_icons.get(asset, "🪙")
        b.button(text=f"{icon} {asset}", callback_data=f"asset_{asset}")
    b.adjust(3)
    b.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_topup"))
    return b.as_markup()

def payment_kb(pay_url: str):
    b = InlineKeyboardBuilder()
    b.add(_btn("Оплатить", url=pay_url, emoji_key="wallet"))
    b.add(_btn("Проверить оплату", cb="check_payment", emoji_key="check"))
    b.adjust(1)
    return b.as_markup()

# ── ИСТОРИЯ ───────────────────────────────────────────────────────────────────
def history_kb(purchases):
    b = InlineKeyboardBuilder()
    for p in purchases:
        b.add(_btn(
            f"#{p.id} · {p.purchased_at.strftime('%d.%m %H:%M')} · {p.price:.2f}$",
            cb=f"hist_{p.id}", emoji_key="box"
        ))
    b.add(_btn("Назад", cb="profile_back", emoji_key="down"))
    b.adjust(1)
    return b.as_markup()

def purchase_detail_kb(purchase_id: int, can_review: bool):
    b = InlineKeyboardBuilder()
    if can_review:
        b.add(_btn("Оставить отзыв", cb=f"leave_review_{purchase_id}", emoji_key="star"))
    b.add(_btn("Назад", cb="profile_history", emoji_key="down"))
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
        _btn("Отправить заявку", cb="unban_confirm", emoji_key="check"),
        _btn("Отмена",           cb="unban_cancel",  emoji_key="ban"),
    ]])

def replace_action_kb(req_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        _btn("Одобрить",  cb=f"replace_approve_{req_id}", emoji_key="check"),
        _btn("Отклонить", cb=f"replace_reject_{req_id}",  emoji_key="ban"),
    ]])

def unban_action_kb(req_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        _btn("Одобрить",  cb=f"unban_approve_{req_id}", emoji_key="unlock"),
        _btn("Отклонить", cb=f"unban_reject_{req_id}",  emoji_key="ban"),
    ]])

# ── ЗАБАНЕН ───────────────────────────────────────────────────────────────────
def banned_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        _btn("Подать апелляцию", cb="unban_request", emoji_key="unlock")
    ]])

# ── АДМИН ─────────────────────────────────────────────────────────────────────
def admin_main_kb():
    b = InlineKeyboardBuilder()
    rows = [
        ("━━━ 📦 ТОВАРЫ ━━━",        "admin_noop",           None),
        ("Добавить товар",            "admin_add_product",    "plus"),
        ("Пополнить товар",           "admin_refill_product", "box"),
        ("Загрузить TXT",             "admin_bulk_product",   "download"),
        ("Изменить описание",         "admin_edit_desc",      "palette"),
        ("Изменить цену",             "admin_edit_price",     "wallet"),
        ("Массово изменить цены",     "admin_bulk_price",     "chart"),
        ("Удалить строки",            "admin_delete_lines",   "trash"),
        ("Удалить товар",             "admin_delete_product", "trash"),
        ("━━━ 📁 КАТЕГОРИИ ━━━",     "admin_noop",           None),
        ("Добавить категорию",        "admin_add_category",   "plus"),
        ("Удалить категорию",         "admin_delete_category","trash"),
        ("━━━ 👥 ПОЛЬЗОВАТЕЛИ ━━━",  "admin_noop",           None),
        ("Найти пользователя",        "user_search",          "search"),
        ("Изменить баланс",           "user_balance",         "wallet"),
        ("Бан / Разбан",              "user_ban",             "ban"),
        ("Изменить кэшбек",           "user_cashback",        "star"),
        ("Топ покупателей",           "admin_top_buyers",     "crown"),
        ("━━━ 📋 ЗАЯВКИ ━━━",        "admin_noop",           None),
        ("Замены",                    "admin_replaces",       "hammer"),
        ("Разблокировки",             "admin_unbans",         "unlock"),
        ("━━━ 🎁 ПРОМОКОДЫ ━━━",     "admin_noop",           None),
        ("Создать промокод",          "promo_add",            "plus"),
        ("Удалить промокод",          "promo_delete",         "trash"),
        ("Список промокодов",         "promo_list",           "books"),
        ("━━━ 📢 РАССЫЛКА ━━━",      "admin_noop",           None),
        ("Новая рассылка",            "admin_broadcast",      "mega"),
        ("Запланированные",           "admin_scheduled",      "clock"),
        ("━━━ 📊 АНАЛИТИКА ━━━",     "admin_noop",           None),
        ("Статистика",                "admin_stats",          "chart"),
        ("Логи покупок",              "admin_view_logs",      "books"),
        ("━━━ 🗄 БАЗА ДАННЫХ ━━━",   "admin_noop",           None),
        ("Экспорт БД",               "admin_export",         "up"),
        ("Импорт БД",                "admin_import",         "download"),
    ]
    for label, cb, emoji in rows:
        b.add(_btn(label, cb=cb, emoji_key=emoji))
    b.adjust(1)
    return b.as_markup()

def admin_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        _btn("Назад в меню", cb="admin_back", emoji_key="home")
    ]])

def admin_promos_kb():
    b = InlineKeyboardBuilder()
    b.add(_btn("Создать", cb="promo_add",    emoji_key="plus"))
    b.add(_btn("Удалить", cb="promo_delete", emoji_key="trash"))
    b.add(_btn("Список",  cb="promo_list",   emoji_key="books"))
    b.add(_btn("Назад",   cb="admin_back",   emoji_key="home"))
    b.adjust(2)
    return b.as_markup()

def admin_users_kb():
    b = InlineKeyboardBuilder()
    b.add(_btn("Найти",      cb="user_search",   emoji_key="search"))
    b.add(_btn("Баланс",     cb="user_balance",  emoji_key="wallet"))
    b.add(_btn("Бан/Разбан", cb="user_ban",      emoji_key="ban"))
    b.add(_btn("Кэшбек",     cb="user_cashback", emoji_key="star"))
    b.add(_btn("Назад",      cb="admin_back",    emoji_key="home"))
    b.adjust(2)
    return b.as_markup()

def broadcast_timing_kb():
    b = InlineKeyboardBuilder()
    b.add(_btn("Отправить сейчас", cb="broadcast_now",      emoji_key="mega"))
    b.add(_btn("Запланировать",    cb="broadcast_schedule", emoji_key="clock"))
    b.add(_btn("Назад",            cb="admin_back",         emoji_key="home"))
    b.adjust(2)
    return b.as_markup()
PYEOF
echo "ok"
