from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton as IBtn,
    ReplyKeyboardMarkup, KeyboardButton as KBtn,
    ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import CRYPTO_ASSETS, ASSET_EMOJI, E, eb

# ── ХЕЛПЕРЫ ───────────────────────────────────────────────────────────────────
def ibtn(text: str, cb: str = None, url: str = None) -> IBtn:
    if url:
        return IBtn(text=text, url=url)
    return IBtn(text=text, callback_data=cb)

def _kb(*rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(r) for r in rows])

def _rkb(*rows, resize=True) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[list(r) for r in rows], resize_keyboard=resize)

def remove_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()

# ── ГЛАВНОЕ МЕНЮ ──────────────────────────────────────────────────────────────
def main_reply(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KBtn(text="📁 Каталог"),   KBtn(text="👤 Профиль")],
        [KBtn(text="🔨 Замена"),    KBtn(text="ℹ️ Поддержка")],
        [KBtn(text="⭐️ Скидка")],
    ]
    if is_admin:
        rows.append([KBtn(text="⚙️ Админ")])
    return _rkb(*rows)

def to_main() -> InlineKeyboardMarkup:
    return _kb([ibtn("🏠 Главное меню", "m_main")])

def back_to_main() -> InlineKeyboardMarkup:
    return _kb([ibtn("◀️ Назад", "m_main")])

# ── КАПЧА ─────────────────────────────────────────────────────────────────────
def captcha_kb(options: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for o in options:
        b.button(text=str(o), callback_data=f"cap_{o}")
    b.adjust(3)
    return b.as_markup()

# ── КАТАЛОГ ───────────────────────────────────────────────────────────────────
def categories(cats) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for c in cats:
        b.button(text=f"📁 {c.name}", callback_data=f"cat_{c.id}")
    b.adjust(1)
    b.row(ibtn("◀️ Назад", "m_main"))
    return b.as_markup()

def products(prods) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in prods:
        qty = "∞" if p.quantity == 0 else str(p.quantity)
        status = "✅" if p.is_available else "❌"
        b.button(text=f"{status} {p.name} | {p.price}$ [{qty}]", callback_data=f"prod_{p.id}")
    b.adjust(1)
    b.row(ibtn("◀️ Назад", "cats_back"))
    return b.as_markup()

def product_view(pid: int, out_of_stock=False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if not out_of_stock:
        b.button(text="🛒 Купить", callback_data=f"buy_{pid}")
    else:
        b.button(text="🔔 Уведомить о поступлении", callback_data=f"notify_{pid}")
    b.button(text="⭐️ Отзывы", callback_data=f"revs_{pid}")
    b.button(text="◀️ Назад", callback_data="cats_back")
    b.button(text="🏠 Главное меню", callback_data="m_main")
    b.adjust(1)
    return b.as_markup()

def amount_pick(pid: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for n in [1, 2, 3, 5, 10]:
        b.button(text=str(n), callback_data=f"qa_{pid}_{n}")
    b.button(text="◀️ Отмена", callback_data=f"prod_{pid}")
    b.adjust(5, 1)
    return b.as_markup()

# ── ПРОФИЛЬ ───────────────────────────────────────────────────────────────────
def profile() -> InlineKeyboardMarkup:
    return _kb(
        [ibtn("👝 Пополнить", "p_topup"),    ibtn("📚 История", "p_history")],
        [ibtn("🎁 Промокод", "p_promo"),      ibtn("🔗 Реферал", "p_ref")],
        [ibtn("◀️ Главное меню", "m_main")],
    )

# ── ПОПОЛНЕНИЕ ────────────────────────────────────────────────────────────────
def choose_asset() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for asset in CRYPTO_ASSETS:
        b.button(text=f"🪙 {asset}", callback_data=f"asset_{asset}")
    b.button(text="◀️ Назад", callback_data="m_profile")
    b.adjust(2)
    return b.as_markup()

def pay_link(url: str) -> InlineKeyboardMarkup:
    return _kb(
        [ibtn("💳 Оплатить", url=url)],
        [ibtn("✅ Проверить оплату", "check_pay")],
        [ibtn("◀️ Главное меню", "m_main")],
    )

# ── ИСТОРИЯ ───────────────────────────────────────────────────────────────────
def history(purchases) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in purchases:
        b.button(text=f"#{p.id} | {p.purchased_at.strftime('%d.%m %H:%M')} | {p.price:.2f}$",
                 callback_data=f"ph_{p.id}")
    b.button(text="◀️ Назад", callback_data="m_profile")
    b.adjust(1)
    return b.as_markup()

def purchase_detail(pid: int, can_review: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if can_review:
        b.button(text="⭐️ Оставить отзыв", callback_data=f"rev_{pid}")
    b.button(text="◀️ Назад", callback_data="p_history")
    b.button(text="🏠 Главное меню", callback_data="m_main")
    b.adjust(1)
    return b.as_markup()

def review_rating(pid: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i in range(1, 6):
        b.button(text="⭐️" * i, callback_data=f"rate_{pid}_{i}")
    b.button(text="◀️ Отмена", callback_data=f"ph_{pid}")
    b.adjust(1)
    return b.as_markup()

# ── БАН / РАЗБАН ──────────────────────────────────────────────────────────────
def banned_kb() -> InlineKeyboardMarkup:
    return _kb([ibtn("📋 Подать апелляцию", "unban_start")])

def appeal() -> InlineKeyboardMarkup:
    return _kb([ibtn("📋 Попробовать снова", "unban_start")])

def unban_confirm() -> InlineKeyboardMarkup:
    return _kb(
        [ibtn("✅ Отправить заявку", "unban_send")],
        [ibtn("❌ Отмена", "m_main")],
    )

# ── ЗАМЕНЫ / РАЗБАНЫ (для админа) ────────────────────────────────────────────
def replace_action(rid: int) -> InlineKeyboardMarkup:
    return _kb(
        [ibtn("✅ Одобрить", f"ra_{rid}"), ibtn("❌ Отклонить", f"rr_{rid}")],
    )

def unban_action(rid: int) -> InlineKeyboardMarkup:
    return _kb(
        [ibtn("✅ Разблокировать", f"ua_{rid}"), ibtn("❌ Отклонить", f"ur_{rid}")],
    )

# ── СКИДКА ────────────────────────────────────────────────────────────────────
def after_spin() -> InlineKeyboardMarkup:
    return _kb(
        [ibtn("🛒 В каталог", "m_catalog")],
        [ibtn("🏠 Главное меню", "m_main")],
    )

# ── ADMIN KEYBOARDS ───────────────────────────────────────────────────────────
def admin_back_btn() -> InlineKeyboardMarkup:
    return _kb([ibtn("◀️ Назад в меню", "admin_back")])

def admin_main() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    sections = [
        # (текст кнопки, callback_data)
        ("━━━ 📦 ТОВАРЫ ━━━",           "admin_noop"),
        ("➕ Добавить товар",             "a_add_prod"),
        ("📥 Пополнить товар",           "a_refill"),
        ("🗂 Загрузить TXT",             "a_bulk_txt"),
        ("📝 Изменить описание",         "a_edit_desc"),
        ("💰 Изменить цену",             "a_edit_price"),
        ("📊 Массово изменить цены",     "a_bulk_price"),
        ("🗑 Удалить строки",            "a_del_lines"),
        ("🗑 Удалить товар",             "a_del_prod"),
        ("━━━ 📁 КАТЕГОРИИ ━━━",        "admin_noop"),
        ("➕ Добавить категорию",         "a_add_cat"),
        ("🗑 Удалить категорию",         "a_del_cat"),
        ("━━━ 👥 ПОЛЬЗОВАТЕЛИ ━━━",     "admin_noop"),
        ("🔍 Найти пользователя",        "a_user_find"),
        ("💰 Изменить баланс",           "a_user_bal"),
        ("🚫 Бан / Разбан",              "a_user_ban"),
        ("⭐️ Изменить кэшбек",          "a_user_cb"),
        ("🏆 Топ покупателей",           "a_top"),
        ("━━━ 📋 ЗАЯВКИ ━━━",           "admin_noop"),
        ("🔨 Замены",                    "a_replaces"),
        ("🔓 Разблокировки",             "admin_unbans"),
        ("━━━ 🎁 ПРОМОКОДЫ ━━━",        "admin_noop"),
        ("➕ Создать промокод",           "a_promo_add"),
        ("🗑 Удалить промокод",          "a_promo_del"),
        ("📋 Список промокодов",         "a_promo_list"),
        ("━━━ 📢 РАССЫЛКА ━━━",         "admin_noop"),
        ("📨 Новая рассылка",            "admin_broadcast"),
        ("📅 Запланированные",           "admin_scheduled"),
        ("━━━ 📊 АНАЛИТИКА ━━━",        "admin_noop"),
        ("📊 Статистика",                "admin_stats"),
        ("📚 Логи покупок",              "admin_view_logs"),
        ("━━━ 🗄 БАЗА ДАННЫХ ━━━",      "admin_noop"),
        ("📤 Экспорт БД",               "admin_export"),
        ("📥 Импорт БД",                "admin_import"),
    ]
    for label, cb in sections:
        b.button(text=label, callback_data=cb)
    b.adjust(1)
    return b.as_markup()

def admin_promos() -> InlineKeyboardMarkup:
    return _kb(
        [ibtn("➕ Создать", "a_promo_add"), ibtn("🗑 Удалить", "a_promo_del")],
        [ibtn("📋 Список",  "a_promo_list")],
        [ibtn("◀️ Назад",   "admin_back")],
    )

def admin_users() -> InlineKeyboardMarkup:
    return _kb(
        [ibtn("🔍 Найти",      "a_user_find"), ibtn("💰 Баланс",  "a_user_bal")],
        [ibtn("🚫 Бан/Разбан", "a_user_ban"),  ibtn("⭐️ Кэшбек", "a_user_cb")],
        [ibtn("◀️ Назад",      "admin_back")],
    )

def broadcast_timing() -> InlineKeyboardMarkup:
    return _kb(
        [ibtn("📨 Отправить сейчас",  "broadcast_now")],
        [ibtn("📅 Запланировать",     "broadcast_schedule")],
        [ibtn("◀️ Назад",            "admin_back")],
    )

# алиасы для совместимости
admin_main_kb    = admin_main
admin_back_kb    = admin_back_btn
admin_promos_kb  = admin_promos
admin_users_kb   = admin_users
broadcast_timing_kb = broadcast_timing
unban_action_kb  = unban_action
PYEOF
