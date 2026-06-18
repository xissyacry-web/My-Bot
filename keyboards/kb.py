"""Единый файл всех клавиатур — с кастомными tgp эмодзи и цветными кнопками"""
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton as IBtn,
    ReplyKeyboardMarkup, KeyboardButton as KBtn,
    ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import CRYPTO_ASSETS, ASSET_EMOJI, E

# ── ХЕЛПЕРЫ ───────────────────────────────────────────────────────────────────
def ibtn(text: str, cb: str = None, url: str = None, emoji_key: str = None, style: str = None) -> IBtn:
    """
    Inline-кнопка с поддержкой:
    - emoji_key: ключ из E (config.py) → icon_custom_emoji_id
    - style: 'primary' (синий) / 'success' (зелёный) / 'danger' (красный) / None (серый)
    """
    kwargs = {"text": text}
    if url:
        kwargs["url"] = url
    else:
        kwargs["callback_data"] = cb
    if emoji_key and emoji_key in E:
        kwargs["icon_custom_emoji_id"] = E[emoji_key][0]
    if style:
        kwargs["style"] = style
    return IBtn(**kwargs)

def kbtn(text: str, emoji_key: str = None) -> KBtn:
    """Reply-кнопка с кастомным tgp эмодзи"""
    if emoji_key and emoji_key in E:
        try:
            return KBtn(text=text, icon_custom_emoji_id=E[emoji_key][0])
        except Exception:
            return KBtn(text=text)
    return KBtn(text=text)

def _kb(*rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(r) for r in rows])

def _rkb(*rows, resize=True, one_time=False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[list(r) for r in rows],
        resize_keyboard=resize,
        one_time_keyboard=one_time
    )

# ── ГЛАВНОЕ МЕНЮ (Reply с tgp эмодзи) ────────────────────────────────────────
def main_reply() -> ReplyKeyboardMarkup:
    return _rkb(
        [kbtn("Каталог",   "folder"),  kbtn("Профиль",   "user")],
        [kbtn("Замена",    "hammer"),  kbtn("Поддержка", "info")],
        [kbtn("Скидка",    "star")],
    )

def admin_reply() -> ReplyKeyboardMarkup:
    return _rkb(
        [kbtn("Каталог",   "folder"),  kbtn("Профиль",   "user")],
        [kbtn("Замена",    "hammer"),  kbtn("Поддержка", "info")],
        [kbtn("Скидка",    "star"),    kbtn("Панель",    "crown")],
    )

def remove_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()

def main_inline() -> InlineKeyboardMarkup:
    return _kb(
        [ibtn("Каталог",   "m_catalog",  emoji_key="folder", style="primary"),
         ibtn("Профиль",   "m_profile",  emoji_key="user",   style="primary")],
        [ibtn("Замена",    "m_replace",  emoji_key="hammer"),
         ibtn("Поддержка", "m_support",  emoji_key="info")],
        [ibtn("Скидка",    "m_discount", emoji_key="star",   style="success")],
    )

def to_main() -> InlineKeyboardMarkup:
    return _kb([ibtn("Главное меню", "m_main", emoji_key="home", style="primary")])

# ── КАПЧА ─────────────────────────────────────────────────────────────────────
def captcha_kb(options: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for opt in options:
        b.add(ibtn(str(opt), f"cap_{opt}"))
    b.adjust(3)
    return b.as_markup()

# ── КАТАЛОГ ───────────────────────────────────────────────────────────────────
def categories(cats) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for c in cats:
        b.add(ibtn(c.name, f"cat_{c.id}", emoji_key="folder"))
    b.adjust(2)
    b.row(ibtn("Главное меню", "m_main", emoji_key="home", style="primary"))
    return b.as_markup()

def products(prods) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in prods:
        qty = "∞" if p.quantity == 0 else str(p.quantity)
        avg = f" ⭐{p.rating_sum/p.rating_count:.1f}" if p.rating_count else ""
        b.add(ibtn(f"{p.name}  💰{p.price}$  [{qty}]{avg}", f"prod_{p.id}", emoji_key="box"))
    b.adjust(1)
    b.row(ibtn("Назад", "cats_back", emoji_key="down"))
    return b.as_markup()

def product_view(pid: int, out_of_stock=False) -> InlineKeyboardMarkup:
    rows = []
    if out_of_stock:
        rows.append([ibtn("Уведомить о наличии", f"notify_{pid}", emoji_key="bell")])
    else:
        rows.append([ibtn("Купить", f"buy_{pid}", emoji_key="cart", style="success")])
    rows.append([
        ibtn("Отзывы", f"revs_{pid}", emoji_key="star"),
        ibtn("Назад",  "cats_back",   emoji_key="down"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def amount_pick(pid: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for n in [1, 2, 5, 10]:
        b.add(ibtn(str(n), f"qa_{pid}_{n}"))
    b.adjust(4)
    return b.as_markup()

# ── ПРОФИЛЬ ───────────────────────────────────────────────────────────────────
def profile() -> InlineKeyboardMarkup:
    return _kb(
        [ibtn("Пополнить баланс", "p_topup",   emoji_key="wallet", style="success")],
        [ibtn("Промокод",          "p_promo",   emoji_key="gift")],
        [ibtn("История покупок",   "p_history", emoji_key="books")],
        [ibtn("Реф. ссылка",       "p_ref",     emoji_key="link")],
        [ibtn("Главное меню",      "m_main",    emoji_key="home", style="primary")],
    )

# ── ОПЛАТА ────────────────────────────────────────────────────────────────────
def choose_asset() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    coin_keys = {"USDT":"coin_usdt","TON":"coin_ton","BTC":"coin_btc",
                "ETH":"coin_eth","LTC":"coin_ltc","BNB":"coin_bnb","TRX":"coin_trx"}
    for a in CRYPTO_ASSETS:
        ek = coin_keys.get(a)
        b.add(ibtn(a, f"asset_{a}", emoji_key=ek))
    b.adjust(3)
    b.row(ibtn("Отмена", "m_main", emoji_key="ban", style="danger"))
    return b.as_markup()

def pay_link(url: str) -> InlineKeyboardMarkup:
    return _kb(
        [ibtn("Оплатить", url=url, emoji_key="wallet", style="success")],
        [ibtn("Проверить оплату", "check_pay", emoji_key="check", style="primary")],
        [ibtn("Назад", "m_main", emoji_key="down")],
    )

# ── ИСТОРИЯ ───────────────────────────────────────────────────────────────────
def history(purchases) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in purchases:
        b.add(ibtn(
            f"#{p.id} · {p.purchased_at.strftime('%d.%m %H:%M')} · {p.price:.2f}$",
            f"ph_{p.id}", emoji_key="box"
        ))
    b.adjust(1)
    b.row(ibtn("Назад", "m_profile", emoji_key="down"))
    return b.as_markup()

def purchase_detail(pid: int, can_review: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_review:
        rows.append([ibtn("Оставить отзыв", f"rev_{pid}", emoji_key="star")])
    rows.append([ibtn("Назад", "p_history", emoji_key="down")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def review_rating(pid: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i in range(1, 6):
        b.add(ibtn("⭐"*i, f"rate_{pid}_{i}"))
    b.adjust(5)
    return b.as_markup()

# ── ЗАМЕНА / РАЗБАН ───────────────────────────────────────────────────────────
def appeal() -> InlineKeyboardMarkup:
    return _kb([ibtn("Подать апелляцию", "unban_start", emoji_key="unlock", style="primary")])

def banned_kb() -> InlineKeyboardMarkup:
    return _kb([ibtn("Подать апелляцию на разблокировку", "unban_start", emoji_key="unlock", style="primary")])

def unban_confirm() -> InlineKeyboardMarkup:
    return _kb([
        ibtn("Отправить", "unban_send", emoji_key="check", style="success"),
        ibtn("Отмена",    "m_main",     emoji_key="ban",   style="danger"),
    ])

def replace_action(rid: int) -> InlineKeyboardMarkup:
    return _kb([
        ibtn("Одобрить",  f"ra_{rid}", emoji_key="check", style="success"),
        ibtn("Отклонить", f"rr_{rid}", emoji_key="ban",   style="danger"),
    ])

def unban_action(rid: int) -> InlineKeyboardMarkup:
    return _kb([
        ibtn("Разбанить", f"ua_{rid}", emoji_key="unlock", style="success"),
        ibtn("Отклонить", f"ur_{rid}", emoji_key="ban",    style="danger"),
    ])

def after_spin() -> InlineKeyboardMarkup:
    return _kb([ibtn("Главное меню", "m_main", emoji_key="home", style="primary")])

# ── АДМИН ─────────────────────────────────────────────────────────────────────
def admin_main() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    items = [
        ("➕ Добавить товар",         "a_add_prod",   "plus" if "plus" in E else None, "success"),
        ("📥 Пополнить товар",        "a_refill",     "box",     None),
        ("🗂 Загрузить TXT",          "a_bulk_txt",   "download",None),
        ("📝 Изменить описание",      "a_edit_desc",  "palette", None),
        ("💰 Изменить цену",          "a_edit_price", "wallet",  None),
        ("📊 Массово изменить цены",  "a_bulk_price", "chart",   None),
        ("🗑 Удалить строки",         "a_del_lines",  "trash",   "danger"),
        ("🗑 Удалить товар",          "a_del_prod",   "trash",   "danger"),
        ("➕ Добавить категорию",      "a_add_cat",    None,      "success"),
        ("🗑 Удалить категорию",      "a_del_cat",    "trash",   "danger"),
        ("🔍 Найти пользователя",     "a_user_find",  "search",  None),
        ("💰 Изменить баланс",        "a_user_bal",   "wallet",  None),
        ("🚫 Бан / Разбан",           "user_ban",     "ban",     "danger"),
        ("⭐ Изменить кэшбек",        "user_cashback","star",    None),
        ("🏆 Топ покупателей",        "a_top",        "crown",   None),
        ("♻️ Замены",                 "admin_replaces", "hammer", None),
        ("🔓 Разблокировки",          "admin_unbans",   "unlock", None),
        ("➕ Создать промокод",        "a_promo_add",    None,    "success"),
        ("🗑 Удалить промокод",       "a_promo_del",    "trash",  "danger"),
        ("📋 Список промокодов",      "a_promo_list",   "books",  None),
        ("📨 Новая рассылка",         "admin_broadcast","mega",   None),
        ("📅 Запланированные",        "admin_scheduled","clock",  None),
        ("📊 Статистика",             "admin_stats",    "chart",  None),
        ("📜 Логи покупок",           "admin_view_logs","books",  None),
        ("📤 Экспорт БД",            "admin_export",   "up",     None),
        ("📥 Импорт БД",             "admin_import",   "download",None),
    ]
    for label, cb, ek, st in items:
        b.add(ibtn(label, cb, emoji_key=ek, style=st))
    b.adjust(1)
    return b.as_markup()

admin_main_kb = admin_main

def admin_back() -> InlineKeyboardMarkup:
    return _kb([ibtn("Назад в меню", "admin_back", emoji_key="home", style="primary")])

admin_back_kb = admin_back

def admin_promos() -> InlineKeyboardMarkup:
    return _kb(
        [ibtn("Создать", "a_promo_add", emoji_key="gift", style="success"),
         ibtn("Удалить", "a_promo_del", emoji_key="trash", style="danger")],
        [ibtn("Список",  "a_promo_list", emoji_key="books")],
        [ibtn("Назад",   "admin_back",   emoji_key="home", style="primary")],
    )

admin_promos_kb = admin_promos

def admin_users() -> InlineKeyboardMarkup:
    return _kb(
        [ibtn("Найти",      "a_user_find", emoji_key="search"),
         ibtn("Баланс",     "a_user_bal",  emoji_key="wallet")],
        [ibtn("Бан/Разбан", "user_ban",    emoji_key="ban", style="danger"),
         ibtn("Кэшбек",     "user_cashback", emoji_key="star")],
        [ibtn("Назад",      "admin_back",  emoji_key="home", style="primary")],
    )

admin_users_kb = admin_users

def broadcast_timing() -> InlineKeyboardMarkup:
    return _kb(
        [ibtn("Отправить сейчас", "bc_now", emoji_key="mega", style="success")],
        [ibtn("Запланировать",     "bc_schedule", emoji_key="clock", style="primary")],
        [ibtn("Назад",            "admin_back", emoji_key="home")],
    )

broadcast_timing_kb = broadcast_timing

def unban_action_kb(rid: int) -> InlineKeyboardMarkup:
    return unban_action(rid)
