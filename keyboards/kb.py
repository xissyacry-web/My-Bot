from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton as IBtn,
    ReplyKeyboardMarkup, KeyboardButton as KBtn,
    ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from config import CRYPTO_ASSETS, ASSET_EMOJI, E

# ── ХЕЛПЕРЫ ───────────────────────────────────────────────────────────────────
def ibtn(text: str, cb: str = None, url: str = None) -> IBtn:
    if url: return IBtn(text=text, url=url)
    return IBtn(text=text, callback_data=cb)

def kbtn(text: str, emoji_id: str = None) -> KBtn:
    """Reply-кнопка с tgp-эмодзи через icon_custom_emoji_id"""
    if emoji_id:
        return KBtn(text=text, icon_custom_emoji_id=emoji_id)
    return KBtn(text=text)

def _kb(*rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(r) for r in rows])

def _rkb(*rows, resize=True, one_time=False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[list(r) for r in rows],
                               resize_keyboard=resize, one_time_keyboard=one_time)

# ── ГЛАВНОЕ МЕНЮ (Reply с tgp эмодзи) ────────────────────────────────────────
def main_reply():
    """Reply клавиатура с tgp эмодзи иконками"""
    return _rkb(
        [kbtn("Каталог",   E["folder"][0]),   kbtn("Профиль",   E["user"][0])],
        [kbtn("Замена",    E["hammer"][0]),    kbtn("Поддержка", E["info"][0])],
        [kbtn("Скидка",    E["star"][0])],
    )

def remove_kb():
    return ReplyKeyboardRemove()

# ── INLINE ГЛАВНОЕ МЕНЮ (запасной вариант) ────────────────────────────────────
def main_inline():
    return _kb(
        [ibtn("📁 Каталог",   "m_catalog"),  ibtn("👤 Профиль",   "m_profile")],
        [ibtn("🔨 Замена",    "m_replace"),  ibtn("ℹ️ Поддержка", "m_support")],
        [ibtn("⭐ Скидка",    "m_discount")],
    )

def to_main():
    return _kb([ibtn("🏠 Главное меню", "m_main")])

# ── КАПЧА ─────────────────────────────────────────────────────────────────────
def captcha_kb(options: list[int]):
    """Кнопки с вариантами ответа капчи"""
    b = InlineKeyboardBuilder()
    for opt in options:
        b.add(ibtn(str(opt), f"cap_{opt}"))
    b.adjust(3)
    return b.as_markup()

# ── КАТАЛОГ ───────────────────────────────────────────────────────────────────
def categories(cats):
    b = InlineKeyboardBuilder()
    for c in cats:
        b.add(ibtn(f"📁 {c.name}", f"cat_{c.id}"))
    b.adjust(2)
    b.row(ibtn("🏠 Главное меню", "m_main"))
    return b.as_markup()

def products(prods):
    b = InlineKeyboardBuilder()
    for p in prods:
        qty = "∞" if p.quantity == 0 else str(p.quantity)
        avg = f" ⭐{p.rating_sum/p.rating_count:.1f}" if p.rating_count else ""
        b.add(ibtn(f"📦 {p.name}  💰{p.price}$  [{qty}]{avg}", f"prod_{p.id}"))
    b.adjust(1)
    b.row(ibtn("◀️ Назад", "cats_back"))
    return b.as_markup()

def product_view(pid: int, out_of_stock=False):
    rows = []
    if out_of_stock:
        rows.append([ibtn("🔔 Уведомить о наличии", f"notify_{pid}")])
    else:
        rows.append([ibtn("🛒 Купить", f"buy_{pid}")])
    rows.append([ibtn("⭐ Отзывы", f"revs_{pid}"), ibtn("◀️ Назад", "cats_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def amount_pick(pid: int):
    b = InlineKeyboardBuilder()
    for n in [1, 2, 5, 10]:
        b.add(ibtn(str(n), f"qa_{pid}_{n}"))
    b.adjust(4)
    return b.as_markup()

# ── ПРОФИЛЬ ───────────────────────────────────────────────────────────────────
def profile():
    return _kb(
        [ibtn("💳 Пополнить баланс", "p_topup")],
        [ibtn("🎁 Промокод",          "p_promo")],
        [ibtn("📜 История покупок",   "p_history")],
        [ibtn("🔗 Реф. ссылка",       "p_ref")],
        [ibtn("🏠 Главное меню",      "m_main")],
    )

# ── ОПЛАТА ────────────────────────────────────────────────────────────────────
def choose_asset():
    b = InlineKeyboardBuilder()
    for a in CRYPTO_ASSETS:
        b.add(ibtn(f"{ASSET_EMOJI.get(a,'🪙')} {a}", f"asset_{a}"))
    b.adjust(3)
    b.row(ibtn("❌ Отмена", "m_main"))
    return b.as_markup()

def pay_link(url: str):
    return _kb(
        [ibtn("💳 Оплатить", url=url)],
        [ibtn("🔄 Проверить оплату", "check_pay")],
        [ibtn("◀️ Назад", "m_main")],
    )

# ── ИСТОРИЯ ───────────────────────────────────────────────────────────────────
def history(purchases):
    b = InlineKeyboardBuilder()
    for p in purchases:
        b.add(ibtn(f"📦 #{p.id} · {p.purchased_at.strftime('%d.%m %H:%M')} · {p.price:.2f}$", f"ph_{p.id}"))
    b.adjust(1)
    b.row(ibtn("◀️ Назад", "m_profile"))
    return b.as_markup()

def purchase_detail(pid: int, can_review: bool):
    rows = []
    if can_review:
        rows.append([ibtn("⭐ Оставить отзыв", f"rev_{pid}")])
    rows.append([ibtn("◀️ Назад", "p_history")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def review_rating(pid: int):
    b = InlineKeyboardBuilder()
    for i in range(1, 6):
        b.add(ibtn("⭐"*i, f"rate_{pid}_{i}"))
    b.adjust(5)
    return b.as_markup()

# ── ЗАМЕНА / РАЗБАН ───────────────────────────────────────────────────────────
def appeal():
    return _kb([ibtn("🔓 Подать апелляцию", "unban_start")])

def unban_confirm():
    return _kb([ibtn("✅ Отправить", "unban_send"), ibtn("❌ Отмена", "m_main")])

def replace_action(rid: int):
    return _kb([ibtn("✅ Одобрить", f"ra_{rid}"), ibtn("❌ Отклонить", f"rr_{rid}")])

def unban_action(rid: int):
    return _kb([ibtn("✅ Разбанить", f"ua_{rid}"), ibtn("❌ Отклонить", f"ur_{rid}")])

def after_spin():
    return _kb([ibtn("🏠 Главное меню", "m_main")])

# ── БАН ───────────────────────────────────────────────────────────────────────
def banned_kb():
    return _kb([ibtn("🔓 Подать апелляцию", "unban_start")])

# ── АДМИН ─────────────────────────────────────────────────────────────────────
def admin_main():
    b = InlineKeyboardBuilder()
    items = [
        ("━━━ 📦 ТОВАРЫ ━━━",       "noop"),
        ("➕ Добавить товар",         "a_add_prod"),
        ("📥 Пополнить товар",        "a_refill"),
        ("🗂 Загрузить TXT",          "a_bulk_txt"),
        ("📝 Изменить описание",      "a_edit_desc"),
        ("💰 Изменить цену",          "a_edit_price"),
        ("📊 Массово изменить цены",  "a_bulk_price"),
        ("🗑 Удалить строки",         "a_del_lines"),
        ("🗑 Удалить товар",          "a_del_prod"),
        ("━━━ 📁 КАТЕГОРИИ ━━━",     "noop"),
        ("➕ Добавить категорию",      "a_add_cat"),
        ("🗑 Удалить категорию",      "a_del_cat"),
        ("━━━ 👥 ПОЛЬЗОВАТЕЛИ ━━━",  "noop"),
        ("🔍 Найти пользователя",     "a_user_find"),
        ("💰 Изменить баланс",        "a_user_bal"),
        ("🚫 Бан / Разбан",           "a_user_ban"),
        ("⭐ Изменить кэшбек",        "a_user_cb"),
        ("🏆 Топ покупателей",        "a_top"),
        ("━━━ 📋 ЗАЯВКИ ━━━",        "noop"),
        ("♻️ Замены",                 "a_replaces"),
        ("🔓 Разблокировки",          "a_unbans"),
        ("━━━ 🎁 ПРОМОКОДЫ ━━━",     "noop"),
        ("➕ Создать промокод",        "a_promo_add"),
        ("🗑 Удалить промокод",       "a_promo_del"),
        ("📋 Список промокодов",      "a_promo_list"),
        ("━━━ 📢 РАССЫЛКА ━━━",      "noop"),
        ("📨 Новая рассылка",         "a_broadcast"),
        ("📅 Запланированные",        "a_scheduled"),
        ("━━━ 📊 АНАЛИТИКА ━━━",     "noop"),
        ("📊 Статистика",             "a_stats"),
        ("📜 Логи покупок",           "a_logs"),
        ("━━━ 🗄 БАЗА ДАННЫХ ━━━",   "noop"),
        ("📤 Экспорт БД",            "a_export"),
        ("📥 Импорт БД",             "a_import"),
    ]
    for label, cb in items:
        b.add(ibtn(label, cb))
    b.adjust(1)
    return b.as_markup()

def admin_back():
    return _kb([ibtn("◀️ Назад в меню", "a_back")])

def broadcast_timing():
    return _kb(
        [ibtn("🚀 Отправить сейчас", "bc_now")],
        [ibtn("⏰ Запланировать",     "bc_schedule")],
        [ibtn("◀️ Назад",            "a_back")],
    )
