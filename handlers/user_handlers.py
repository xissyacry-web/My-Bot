import asyncio
import random
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
from sqlalchemy import select

from database.database import AsyncSessionLocal
from database.models import User, Invoice, Promocode, Purchase, Product, UnbanRequest, UserDiscount, Category
from keyboards.reply import main_menu
from keyboards.inline import (
    categories_keyboard, products_keyboard, profile_keyboard,
    payment_keyboard, history_keyboard, unban_confirm_keyboard
)
from services.user_service import get_user, create_user
from services.product_service import get_categories, get_products_by_category, buy_product
from services.payment_service import create_invoice, get_invoice
from services.replace_service import create_replace_request
from services.log_service import log_purchase, log_register, log_refill, log_promo
from utils.states import (
    ReplenishBalance, PromocodeInput, BuyProduct,
    UnbanProcess, ReplaceRequestStates
)
# Импорт состояний админки для полной сборки файла
from utils.states import AdminStates, AddCategory, AddProduct, AddPromo
from config import ADMIN_IDS

router = Router()

# =====================================================================
#  ОБНОВЛЕННЫЙ ТГП ПАК: TRANSLUCENT PACK BY @v7agency
# =====================================================================
E_CROWN   = "5276220667182736074" # 👑 Исправлен ID короны
E_FOLDER  = "5278227821364275264" # 📁
E_BOX     = "5278540791336165644" # 📦
E_CHECK   = "5278411813468269386" # ✅
E_WALLET  = "5276398496008663230" # 👝
E_BOOKS   = "5206626000665868017" # 📚
E_WARNING = "5276240711795107620" # ⚠️
E_USER    = "5275979556308674886" # 👤
E_BRIEF   = "5276037216244624892" # 💼
E_CLOCK   = "5276412364458059956" # 🕓
E_GIFT    = "5276422526350681413" # 🎁
E_BAN     = "5278578973595427038" # 🚫
E_STAR    = "5276111746812112286" # ⭐️
E_INFO    = "5278753302023004775" # ℹ️
E_HAMMER  = "5276314275994954605" # 🔨
E_MINUS   = "5244796895443838315" # ➖
E_PLUS    = "5242329690135356589" # ➕
E_SPIN    = "5278304890257436355" # 🎮
E_NUM_1   = "5244961448525848230" # 1️⃣
E_NUM_2   = "5242293676834579345" # 2️⃣
E_NUM_3   = "5242652525647127686" # 3️⃣

# ── ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ БЕЗОПАСНОЙ ОТПРАВКИ ТГП-ЭМОДЗИ ────────────────
async def safe_answer(message: Message, text_with_tg_emoji: str, fallback_text: str, **kwargs):
    """Пытается отправить текст с кастомными эмодзи, при ошибке отправляет обычный текст"""
    try:
        return await message.answer(text_with_tg_emoji, **kwargs)
    except Exception:
        return await message.answer(fallback_text, **kwargs)

async def safe_edit_text(callback_query: CallbackQuery, text_with_tg_emoji: str, fallback_text: str, **kwargs):
    """Пытается отредактировать текст с кастомными эмодзи, при ошибке отправляет обычный текст"""
    try:
        return await callback_query.message.edit_text(text_with_tg_emoji, **kwargs)
    except Exception:
        return await callback_query.message.edit_text(fallback_text, **kwargs)

# ── HELPERS ───────────────────────────────────────────────────────────────────

async def ensure_user(user_id: int, username: str = None):
    async with AsyncSessionLocal() as session:
        user = await get_user(session, user_id)
        if not user:
            user = await create_user(session, user_id, username)
        return user

async def clear_state(message: Message, state: FSMContext):
    if await state.get_state():
        await state.clear()

async def get_active_discount(session, user_id: int):
    return (await session.execute(
        select(UserDiscount).where(
            UserDiscount.user_id == user_id,
            UserDiscount.expires_at > datetime.utcnow()
        )
    )).scalar_one_or_none()

def get_inline_qty_keyboard(product_id: int, current_qty: int):
    """Генерация клавиатуры счетчика количества товара"""
    kb = [
        [
            InlineKeyboardButton(text=f'<tg-emoji id="{E_MINUS}">➖</tg-emoji>', callback_data=f"pqty:minus:{product_id}:{current_qty}"),
            InlineKeyboardButton(text=f"{current_qty} шт.", callback_data="pqty:ignore"),
            InlineKeyboardButton(text=f'<tg-emoji id="{E_PLUS}">➕</tg-emoji>', callback_data=f"pqty:plus:{product_id}:{current_qty}")
        ],
        [
            InlineKeyboardButton(text=f'<tg-emoji id="{E_CHECK}">✅</tg-emoji> Подтвердить заказ', callback_data=f"pqty:confirm:{product_id}:{current_qty}")
        ],
        [
            InlineKeyboardButton(text="◀️ Назад в каталог", callback_data="back_to_categories")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ── START ─────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await clear_state(message, state)
    async with AsyncSessionLocal() as session:
        user = await get_user(session, message.from_user.id)
        if not user:
            await create_user(session, message.from_user.id, message.from_user.username)
            await log_register(message.bot, message.from_user.id, message.from_user.username)
            
    text_tg = f'<tg-emoji id="{E_CROWN}">👑</tg-emoji> <b>Добро пожаловать!</b>\n\nИспользуй меню ниже ↓'
    text_fb = f'👑 <b>Добро пожаловать!</b>\n\nИспользуй меню ниже ↓'
    await safe_answer(message, text_tg, text_fb, parse_mode="HTML", reply_markup=main_menu())

# ── CATALOG ───────────────────────────────────────────────────────────────────

@router.message(F.text == "📋 Каталог")
async def show_categories(message: Message, state: FSMContext):
    await clear_state(message, state)
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session, parent_id=None)
    if cats:
        text_tg = f'<tg-emoji id="{E_FOLDER}">📁</tg-emoji> <b>Каталог</b>'
        text_fb = f'📁 <b>Каталог</b>'
        await safe_answer(message, text_tg, text_fb, parse_mode="HTML", reply_markup=categories_keyboard(cats))
    else:
        text_tg = f'<tg-emoji id="{E_BOX}">📦</tg-emoji> Каталог пуст'
        text_fb = f'📦 Каталог пуст'
        await safe_answer(message, text_tg, text_fb, parse_mode="HTML")

@router.callback_query(F.data.startswith("cat_"))
async def category_selected(callback: CallbackQuery):
    cat_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        cat = await session.get(Category, cat_id)
        if not cat:
            await callback.answer("Не найдено", show_alert=True)
            return
        subcats = await get_categories(session, parent_id=cat_id)
        if subcats:
            text_tg = f'<tg-emoji id="{E_FOLDER}">📁</tg-emoji> <b>{cat.name}</b>'
            text_fb = f'📁 <b>{cat.name}</b>'
            await safe_edit_text(callback, text_tg, text_fb, parse_mode="HTML", reply_markup=categories_keyboard(subcats))
        else:
            products = await get_products_by_category(session, cat_id)
            if products:
                text_tg = f'<tg-emoji id="{E_FOLDER}">📁</tg-emoji> <b>{cat.name}</b>\n\nВыбери товар:'
                text_fb = f'📁 <b>{cat.name}</b>\n\nВыбери товар:'
                await safe_edit_text(callback, text_tg, text_fb, parse_mode="HTML", reply_markup=products_keyboard(products))
            else:
                await callback.answer("Товаров нет", show_alert=True)
    await callback.answer()

@router.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session, parent_id=None)
    if cats:
        text_tg = f'<tg-emoji id="{E_FOLDER}">📁</tg-emoji> <b>Каталог</b>'
        text_fb = f'📁 <b>Каталог</b>'
        await safe_edit_text(callback, text_tg, text_fb, parse_mode="HTML", reply_markup=categories_keyboard(cats))
    else:
        await callback.message.edit_text("Каталог пуст")
    await callback.answer()

@router.callback_query(F.data.startswith("buy_"))
async def buy_show_product(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        product = await session.get(Product, product_id)
        if not product or not product.is_available:
            await callback.answer("Товар недоступен", show_alert=True)
            return
        qty = "∞" if product.quantity == 0 else str(product.quantity)
        disc = await get_active_discount(session, callback.from_user.id)

        if disc:
            final = round(product.price * (1 - disc.percent / 100), 2)
            price_line = f"💰 <s>{product.price}$</s> → <b>{final}$</b> (-{disc.percent}%)"
        else:
            price_line = f"💰 <b>{product.price}$</b>"

        text_tg = (
            f'<tg-emoji id="{E_BOX}">📦</tg-emoji> <b>{product.name}</b>\n\n'
            f"{product.description or 'Описание отсутствует'}\n\n"
            f"{price_line}\n"
            f'<tg-emoji id="{E_CLOCK}">🕓</tg-emoji> В наличии: {qty} шт.\n\n'
            f"Укажите количество кнопками ниже:"
        )
        text_fb = (
            f'📦 <b>{product.name}</b>\n\n'
            f"{product.description or 'Описание отсутствует'}\n\n"
            f"{price_line}\n"
            f'🕓 В наличии: {qty} шт.\n\n'
            f"Укажите количество кнопками ниже:"
        )
        
    await safe_answer(callback.message, text_tg, text_fb, parse_mode="HTML", reply_markup=get_inline_qty_keyboard(product_id, 1))
    await callback.answer()

# ── ИНТЕРАКТИВНЫЙ ВЫБОР КОЛИЧЕСТВА ТОВАРА ───────────────────────────────────────

@router.callback_query(F.data.startswith("pqty:"))
async def process_qty_change(callback: CallbackQuery, state: FSMContext):
    data = callback.data.split(":")
    action = data[1]
    
    if action == "ignore":
        await callback.answer()
        return
        
    product_id = int(data[2])
    current_qty = int(data[3])
    
    async with AsyncSessionLocal() as session:
        product = await session.get(Product, product_id)
        if not product or not product.is_available:
            await callback.answer("Товар больше недоступен", show_alert=True)
            return
            
        if action == "minus":
            new_qty = max(1, current_qty - 1)
        elif action == "plus":
            if product.quantity > 0 and current_qty >= product.quantity:
                await callback.answer(f"Максимально доступно: {product.quantity} шт.", show_alert=True)
                return
            new_qty = current_qty + 1
            
        elif action == "confirm":
            await callback.answer()
            user_id = callback.from_user.id
            await ensure_user(user_id, callback.from_user.username)
            
            disc = await get_active_discount(session, user_id)
            discount_pct = disc.percent if disc else 0
            result = await buy_product(session, user_id, product_id, current_qty, discount_pct)

            if result["success"]:
                qleft = result.get('quantity_left', 0)
                qleft_str = f"{qleft} шт." if isinstance(qleft, int) and qleft > 0 else "∞"
                
                text_tg = (
                    f'<tg-emoji id="{E_CHECK}">✅</tg-emoji> <b>Куплено {current_qty} шт.</b>\n'
                    f'<tg-emoji id="{E_WALLET}">👝</tg-emoji> Итого: {result.get("total_price", 0):.2f}$\n'
                    f"Баланс: {result['balance']:.2f}$\n"
                    f'<tg-emoji id="{E_BOX}">📦</tg-emoji> Осталось: {qleft_str}'
                )
                text_fb = (
                    f'✅ <b>Куплено {current_qty} шт.</b>\n'
                    f'👝 Итого: {result.get("total_price", 0):.2f}$\n'
                    f"Баланс: {result['balance']:.2f}$\n"
                    f'📦 Осталось: {qleft_str}'
                )
                await safe_edit_text(callback, text_tg, text_fb, parse_mode="HTML")

                if result.get("content"):
                    txt_books_tg = f'<tg-emoji id="{E_BOOKS}">📚</tg-emoji> <b>Ваш товар:</b>\n\n<code>{result["content"]}</code>'
                    txt_books_fb = f'📚 <b>Ваш товар:</b>\n\n<code>{result["content"]}</code>'
                    await safe_answer(callback.message, txt_books_tg, txt_books_fb, parse_mode="HTML")
                if result.get("file_id"):
                    try:
                        await callback.message.answer_document(result["file_id"])
                    except Exception:
                        pass

                await log_purchase(
                    callback.bot, user_id, callback.from_user.username,
                    result['product_name'], current_qty, result.get('total_price', 0),
                    lines=result.get('selected_lines', [])
                )
            else:
                txt_warn_tg = f'<tg-emoji id="{E_WARNING}">⚠️</tg-emoji> {result["error"]}'
                txt_warn_fb = f'⚠️ {result["error"]}'
                await safe_edit_text(callback, txt_warn_tg, txt_warn_fb, parse_mode="HTML")
            return

    if new_qty != current_qty:
        try:
            await callback.message.edit_reply_markup(reply_markup=get_inline_qty_keyboard(product_id, new_qty))
        except Exception:
            pass
    await callback.answer()

# ── PROFILE ───────────────────────────────────────────────────────────────────

@router.message(F.text == "👤 Профиль")
async def profile(message: Message, state: FSMContext):
    await clear_state(message, state)
    user = await ensure_user(message.from_user.id, message.from_user.username)
    async with AsyncSessionLocal() as session:
        disc = await get_active_discount(session, message.from_user.id)
        purchases_count = len((await session.execute(
            select(Purchase).where(Purchase.user_id == message.from_user.id)
        )).scalars().all())

    days = (datetime.utcnow() - user.registered_at).days
    disc_line_tg = ""
    disc_line_fb = ""
    if disc:
        left = disc.expires_at - datetime.utcnow()
        h = int(left.total_seconds() // 3600)
        disc_line_tg = f'\n<tg-emoji id="{E_STAR}">⭐️</tg-emoji> Скидка: <b>{disc.percent}%</b> (ещё {h}ч.)'
        disc_line_fb = f'\n⭐️ Скидка: <b>{disc.percent}%</b> (ещё {h}ч.)'

    text_tg = (
        f'<tg-emoji id="{E_USER}">👤</tg-emoji> <b>Профиль</b>\n\n'
        f"ID: <code>{user.user_id}</code>\n"
        f"Username: @{user.username or '—'}\n"
        f'<tg-emoji id="{E_WALLET}">👝</tg-emoji> Баланс: <b>{user.balance:.2f}$</b>\n'
        f'<tg-emoji id="{E_BRIEF}">💼</tg-emoji> Покупок: {purchases_count}\n'
        f'<tg-emoji id="{E_CLOCK}">🕓</tg-emoji> Дней с нами: {days}'
        f"{disc_line_tg}"
    )
    text_fb = (
        f'👤 <b>Профиль</b>\n\n'
        f"ID: <code>{user.user_id}</code>\n"
        f"Username: @{user.username or '—'}\n"
        f'👝 Баланс: <b>{user.balance:.2f}$</b>\n'
        f'💼 Покупок: {purchases_count}\n'
        f'🕓 Дней с нами: {days}'
        f"{disc_line_fb}"
    )

    await safe_answer(message, text_tg, text_fb, parse_mode="HTML", reply_markup=profile_keyboard())

@router.callback_query(F.data == "profile_back")
async def profile_back(callback: CallbackQuery):
    try:
        await callback.message.edit_reply_markup(reply_markup=profile_keyboard())
    except Exception:
        pass
    await callback.answer()

# ── TOPUP ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "profile_topup")
async def profile_topup(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback.message, f'<tg-emoji id="{E_WALLET}">👝</tg-emoji> Введите сумму пополнения ($):', "👝 Введите сумму пополнения ($):", parse_mode="HTML")
    await state.set_state(ReplenishBalance.amount)
    await callback.answer()

@router.message(ReplenishBalance.amount)
async def process_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError
    except Exception:
        await message.answer("Введите положительное число.")
        return
    try:
        inv = await create_invoice(amount, f"Пополнение {message.from_user.id}")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
        await state.clear()
        return
    async with AsyncSessionLocal() as session:
        session.add(Invoice(user_id=message.from_user.id, invoice_id=inv['invoice_id'], amount=amount))
        await session.commit()
        
    text_tg = f'<tg-emoji id="{E_WALLET}">👝</tg-emoji> Счёт на <b>{amount}$</b> создан.\nОплатите и нажмите «Проверить».'
    text_fb = f'👝 Счёт на <b>{amount}$</b> создан.\nОплатите и нажмите «Проверить».'
    await safe_answer(message, text_tg, text_fb, parse_mode="HTML", reply_markup=payment_keyboard(inv['pay_url']))
    await state.clear()

@router.callback_query(F.data == "check_payment")
async def check_payment(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with AsyncSessionLocal() as session:
        inv = (await session.execute(
            select(Invoice).where(Invoice.user_id == user_id, Invoice.status == 'active')
            .order_by(Invoice.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        if not inv:
            await callback.answer("Нет активных счетов.", show_alert=True)
            return
        data = await get_invoice(inv.invoice_id)
        if data and data['status'] == 'paid':
            inv.status = 'paid'
            user = await session.get(User, user_id)
            user.balance += inv.amount
            await session.commit()
            await safe_answer(callback.message, f'<tg-emoji id="{E_CHECK}">✅</tg-emoji> Зачислено <b>{inv.amount:.2f}$</b>', f'✅ Зачислено <b>{inv.amount:.2f}$</b>', parse_mode="HTML")
            await log_refill(callback.bot, user_id, callback.from_user.username, inv.amount)
        elif data and data['status'] == 'expired':
            inv.status = 'expired'
            await session.commit()
            await safe_answer(callback.message, f'<tg-emoji id="{E_CLOCK}">🕓</tg-emoji> Счёт истёк.', '🕓 Счёт истёк.', parse_mode="HTML")
        else:
            await callback.answer("Оплата не поступила.", show_alert=True)
    await callback.answer()

# ── PROMO ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "profile_promo")
async def promo_start(callback: CallbackQuery, state: FSMContext):
    await safe_answer(callback.message, f'<tg-emoji id="{E_GIFT}">🎁</tg-emoji> Введите промокод:', "🎁 Введите промокод:", parse_mode="HTML")
    await state.set_state(PromocodeInput.code)
    await callback.answer()

@router.message(PromocodeInput.code)
async def promocode_apply(message: Message, state: FSMContext):
    code = message.text.strip()
    user_id = message.from_user.id
    async with AsyncSessionLocal() as session:
        user = await get_user(session, user_id)
        if not user:
            await message.answer("Сначала /start")
            await state.clear()
            return
        promo = await session.get(Promocode, code)
        used = [c.strip() for c in user.used_promocodes.split(',') if c.strip()]
        if code in used:
            await safe_answer(message, f'<tg-emoji id="{E_BAN}">🚫</tg-emoji> Уже использован.', '🚫 Уже использован.', parse_mode="HTML")
        elif not promo or not promo.is_active:
            await safe_answer(message, f'<tg-emoji id="{E_BAN}">🚫</tg-emoji> Недействителен.', '🚫 Недействителен.', parse_mode="HTML")
        elif promo.expires_at and promo.expires_at < datetime.utcnow():
            await safe_answer(message, f'<tg-emoji id="{E_CLOCK}">🕓</tg-emoji> Истёк.', '🕓 Истёк.', parse_mode="HTML")
        elif promo.max_activations is not None and promo.used_count >= promo.max_activations:
            await safe_answer(message, f'<tg-emoji id="{E_BAN}">🚫</tg-emoji> Лимит исчерпан.', '🚫 Лимит исчерпан.', parse_mode="HTML")
        else:
            user.balance += promo.bonus_amount
            promo.used_count += 1
            used.append(code)
            user.used_promocodes = ','.join(used)
            await session.commit()
            await safe_answer(message, f'<tg-emoji id="{E_GIFT}">🎁</tg-emoji> <b>+{promo.bonus_amount:.2f}$</b> на баланс!', f'🎁 <b>+{promo.bonus_amount:.2f}$</b> на баланс!', parse_mode="HTML")
            await log_promo(message.bot, user_id, message.from_user.username, code, promo.bonus_amount)
    await state.clear()

# ── HISTORY ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "profile_history")
async def profile_history(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with AsyncSessionLocal() as session:
        purchases = (await session.execute(
            select(Purchase).where(Purchase.user_id == user_id)
            .order_by(Purchase.purchased_at.desc()).limit(15)
        )).scalars().all()
    if not purchases:
        await callback.answer("Покупок нет.", show_alert=True)
        return
    text_tg = f'<tg-emoji id="{E_BOOKS}">📚</tg-emoji> <b>Покупки</b> — выбери для деталей:'
    text_fb = f'📚 <b>Покупки</b> — выбери для деталей:'
    await safe_edit_text(callback, text_tg, text_fb, parse_mode="HTML", reply_markup=history_keyboard(purchases))
    await callback.answer()

@router.callback_query(F.data.startswith("hist_"))
async def purchase_detail(callback: CallbackQuery):
    purchase_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        p = await session.get(Purchase, purchase_id)
        if not p:
            await callback.answer("Не найдено", show_alert=True)
            return
        product = await session.get(Product, p.product_id)
        pname = product.name if product else "удалённый товар"

    text_tg = (
        f'<tg-emoji id="{E_BOX}">📦</tg-emoji> <b>{pname}</b>\n'
        f"Кол-во: {p.amount} шт.\n"
        f'<tg-emoji id="{E_WALLET}">👝</tg-emoji> {p.price:.2f}$\n'
        f'<tg-emoji id="{E_CLOCK}">🕓</tg-emoji> {p.purchased_at.strftime("%d.%m.%Y %H:%M")}'
    )
    text_fb = (
        f'📦 <b>{pname}</b>\n'
        f"Кол-во: {p.amount} шт.\n"
        f'👝 {p.price:.2f}$\n'
        f'🕓 {p.purchased_at.strftime("%d.%m.%Y %H:%M")}'
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад", callback_data="profile_history")
    ]])
    await safe_edit_text(callback, text_tg, text_fb, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

# ── АНИМИРОВАННАЯ РУЛЕТКА СКИДОК ───────────────────────────────────────────────

@router.message(F.text == "🏷 Скидка")
async def spin_discount(message: Message, state: FSMContext):
    await clear_state(message, state)
    user_id = message.from_user.id
    async with AsyncSessionLocal() as session:
        existing = await get_active_discount(session, user_id)
        if existing:
            left = existing.expires_at - datetime.utcnow()
            h = int(left.total_seconds() // 3600)
            text_tg = (
                f'<tg-emoji id="{E_STAR}">⭐️</tg-emoji> У тебя уже есть активная скидка <b>{existing.percent}%</b>\n'
                f'<tg-emoji id="{E_CLOCK}">🕓</tg-emoji> Действует ещё {h} ч.'
            )
            text_fb = (
                f'⭐️ У тебя уже есть активная скидка <b>{existing.percent}%</b>\n'
                f'🕓 Действует ещё {h} ч.'
            )
            await safe_answer(message, text_tg, text_fb, parse_mode="HTML")
            return

        percent = random.randint(1, 10)
        expires = datetime.utcnow() + timedelta(hours=24)
        old = (await session.execute(
            select(UserDiscount).where(UserDiscount.user_id == user_id)
        )).scalar_one_or_none()
        
        if old:
            old.percent = percent
            old.expires_at = expires
            old.created_at = datetime.utcnow()
        else:
            session.add(UserDiscount(user_id=user_id, percent=percent, expires_at=expires))
        await session.commit()

    frames_tg = [
        f'<tg-emoji id="{E_SPIN}">🎮</tg-emoji> [ 🔄 ВРАЩАЕМ БАРАБАН... ]',
        f'<tg-emoji id="{E_SPIN}">🎮</tg-emoji> [ 🎰 СКИДКА 1% ]',
        f'<tg-emoji id="{E_SPIN}">🎮</tg-emoji> [ 🔥 СКИДКА 10% ]',
        f'<tg-emoji id="{E_SPIN}">🎮</tg-emoji> [ ⚡ СКИДКА 5% ]',
        f'<tg-emoji id="{E_SPIN}">🎮</tg-emoji> [ 🚀 СКИДКА 3% ]',
        f'<tg-emoji id="{E_SPIN}">🎮</tg-emoji> [ 💎 СКИДКА 7% ]',
    ]
    frames_fb = [
        '🎮 [ 🔄 ВРАЩАЕМ БАРАБАН... ]',
        '🎮 [ 🎰 СКИДКА 1% ]',
        '🎮 [ 🔥 СКИДКА 10% ]',
        '🎮 [ ⚡ СКИДКА 5% ]',
        '🎮 [ 🚀 СКИДКА 3% ]',
        '🎮 [ 💎 СКИДКА 7% ]',
    ]
    
    use_tg_emoji = True
    try:
        spin_msg = await message.answer(f'<tg-emoji id="{E_SPIN}">🎮</tg-emoji> <b>Запуск рулетки скидок...</b>', parse_mode="HTML")
    except Exception:
        use_tg_emoji = False
        spin_msg = await message.answer('🎮 <b>Запуск рулетки скидок...</b>', parse_mode="HTML")
    
    for _ in range(2):
        if use_tg_emoji:
            random.shuffle(frames_tg)
            for frame in frames_tg:
                try:
                    await spin_msg.edit_text(f"<b>{frame}</b>", parse_mode="HTML")
                    await asyncio.sleep(0.2)
                except Exception:
                    use_tg_emoji = False
                    break
        if not use_tg_emoji:
            random.shuffle(frames_fb)
            for frame in frames_fb:
                try:
                    await spin_msg.edit_text(f"<b>{frame}</b>", parse_mode="HTML")
                    await asyncio.sleep(0.2)
                except Exception:
                    pass

    res_tg = (
        f'<tg-emoji id="{E_STAR}">⭐️</tg-emoji> Тебе выпала скидка <b>{percent}%</b> на 24 часа!\n\n'
        f'<tg-emoji id="{E_CHECK}">✅</tg-emoji> Применяется автоматически при покупке.'
    )
    res_fb = (
        f'⭐️ Тебе выпала скидка <b>{percent}%</b> на 24 часа!\n\n'
        f'✅ Применяется автоматически при покупке.'
    )
    
    if use_tg_emoji:
        try:
            await spin_msg.edit_text(res_tg, parse_mode="HTML")
        except Exception:
            await spin_msg.edit_text(res_fb, parse_mode="HTML")
    else:
        await spin_msg.edit_text(res_fb, parse_mode="HTML")

# ── SUPPORT ───────────────────────────────────────────────────────────────────

@router.message(F.text == "🆘 Поддержка")
async def support(message: Message, state: FSMContext):
    await clear_state(message, state)
    await safe_answer(message, f'<tg-emoji id="{E_INFO}">ℹ️</tg-emoji> Поддержка: @XissyaSup', "ℹ️ Поддержка: @XissyaSup", parse_mode="HTML")

# ── REPLACE ───────────────────────────────────────────────────────────────────

@router.message(F.text == "♻️ Замена")
async def replace_start(message: Message, state: FSMContext):
    await clear_state(message, state)
    async with AsyncSessionLocal() as session:
        exists = (await session.execute(
            select(Purchase).where(Purchase.user_id == message.from_user.id, Purchase.status == 'completed')
        )).first()
        if not exists:
            await safe_answer(message, f'<tg-emoji id="{E_WARNING}">⚠️</tg-emoji> Нет завершённых покупок.', '⚠️ Нет завершённых покупок.', parse_mode="HTML")
            return
    await safe_answer(message, f'<tg-emoji id="{E_HAMMER}">🔨</tg-emoji> Укажи номер лога и время покупки:', '🔨 Укажи номер лога и время покупки:', parse_mode="HTML")
    await state.set_state(ReplaceRequestStates.log_time)

@router.message(ReplaceRequestStates.log_time)
async def replace_log_time(message: Message, state: FSMContext):
    await state.update_data(log_info=message.text, photos=[])
    await message.answer("Отправляй фото (до 5 шт.), когда закончишь — напиши <b>готово</b>.", parse_mode="HTML")
    await state.set_state(ReplaceRequestStates.photos)

@router.message(ReplaceRequestStates.photos, F.photo)
async def replace_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get('photos', [])
    if len(photos) >= 5:
        await message.answer("Максимум 5. Напиши <b>готово</b>.", parse_mode="HTML")
        return
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(f"Фото {len(photos)}/5 принято.")

@router.message(ReplaceRequestStates.photos, F.text)
async def replace_photos_done(message: Message, state: FSMContext):
    t = message.text.strip().lower()
    if t == "готово":
        data = await state.get_data()
        if not data.get('photos'):
            await message.answer("Фото не отправлено. Отправь фото или напиши «—».")
            return
        await message.answer("Опиши жалобу:")
        await state.set_state(ReplaceRequestStates.complaint)
    elif t == "—":
        await state.update_data(photos=[])
        await message.answer("Ок, без фото. Опиши жалобу:")
        await state.set_state(ReplaceRequestStates.complaint)
    else:
        await message.answer("Отправь фото или напиши <b>готово</b>.", parse_mode="HTML")

@router.message(ReplaceRequestStates.complaint)
async def replace_complaint(message: Message, state: FSMContext):
    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        try:
            req = await create_replace_request(
                session, message.from_user.id,
                data['log_info'], data.get('photos', []), message.text
            )
        except ValueError as e:
            await safe_answer(message, f'<tg-emoji id="{E_WARNING}">⚠️</tg-emoji> {e}', f'⚠️ {e}', parse_mode="HTML")
            await state.clear()
            return
        for admin_id in ADMIN_IDS:
            try:
                caption = (
                    f'<tg-emoji id="{E_HAMMER}">🔨</tg-emoji> Заявка на замену #{req.id}\n'
                    f'<tg-emoji id="{E_USER}">👤</tg-emoji> @{message.from_user.username} ({message.from_user.id})\n'
                    f"Лог: {data['log_info']}\n"
                    f"Жалоба: {message.text}"
                )
                photos = data.get('photos', [])
                if photos:
                    media = [InputMediaPhoto(media=pid) for pid in photos]
                    await message.bot.send_media_group(admin_id, media)
                await message.bot.send_message(
                    admin_id, caption, parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="✅", callback_data=f"replace_approve_{req.id}"),
                        InlineKeyboardButton(text="❌", callback_data=f"replace_reject_{req.id}")
                    ]])
                )
            except Exception as e:
                print(f"Admin notify error: {e}")
                
    await safe_answer(message, f'<tg-emoji id="{E_CHECK}">✅</tg-emoji> Заявка отправлена.', '✅ Заявка отправлена.', parse_mode="HTML")
    await state.clear()

# ── UNBAN ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "unban_request")
async def unban_request(callback: CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as session:
        user = await session.get(User, callback.from_user.id)
        if not user or not user.is_banned:
            await callback.answer("Вы не заблокированы!", show_alert=True)
            return
    await callback.message.answer("Отправь фото доказательства. Если нет — напиши «—».")
    await state.set_state(UnbanProcess.waiting_photos)
    await state.update_data(photos=[])
    await callback.answer()

@router.message(UnbanProcess.waiting_photos, F.photo)
async def unban_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get('photos', [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(f"Фото {len(photos)}. Ещё или напиши <b>готово</b>.", parse_mode="HTML")

@router.message(UnbanProcess.waiting_photos, F.text)
async def unban_photo_text(message: Message, state: FSMContext):
    t = message.text.strip().lower()
    if t in ("готово", "—", "-"):
        await message.answer("Опиши причину разблокировки:")
        await state.set_state(UnbanProcess.waiting_description)
    else:
        await message.answer("Отправь фото или напиши <b>готово</b>.", parse_mode="HTML")

@router.message(UnbanProcess.waiting_description)
async def unban_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Отправить заявку?", reply_markup=unban_confirm_keyboard())
    await state.set_state(UnbanProcess.confirm)

@router.callback_query(UnbanProcess.confirm, F.data == "unban_confirm")
async def unban_confirm_cb(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id
    async with AsyncSessionLocal() as session:
        req = UnbanRequest(
            user_id=user_id,
            photos=','.join(data.get('photos', [])) or None,
            description=data.get('description', '-')
        )
        session.add(req)
        await session.commit()
        for admin_id in ADMIN_IDS:
            try:
                photos = data.get('photos', [])
                if photos:
                    media = [InputMediaPhoto(media=pid) for pid in photos]
                    await callback.bot.send_media_group(admin_id, media)
                await callback.bot.send_message(
                    admin_id,
                    f'🔓 Разблокировка #{req.id}\n'
                    f"@{callback.from_user.username} ({user_id})\n"
                    f"{data.get('description', '-')}",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="✅ Одобрить", callback_data=f"unban_approve_{req.id}"),
                        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"unban_reject_{req.id}")
                    ]])
                )
            except Exception as e:
                print(f"Admin unban notify error: {e}")
                
    await safe_answer(callback.message, f'<tg-emoji id="{E_CHECK}">✅</tg-emoji> Заявка отправлена.', '✅ Заявка отправлена.', parse_mode="HTML")
    await state.clear()

@router.callback_query(UnbanProcess.confirm, F.data == "unban_cancel")
async def unban_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Отменено.")
    await state.clear()

@router.callback_query(F.data == "unban_ignore")
async def unban_ignore(callback: CallbackQuery):
    await callback.answer()


# =====================================================================
#  ВТОРАЯ (АДМИНСКАЯ) ЧАСТЬ ФАЙЛА — ПОЛНОЕ ВОССТАНОВЛЕНИЕ С ТГП-ЭМОДЗИ
# =====================================================================

def get_admin_keyboard():
    kb = [
        [InlineKeyboardButton(text="📁 Добавить категорию", callback_data="admin_add_cat")],
        [InlineKeyboardButton(text="📦 Добавить товар", callback_data="admin_add_prod")],
        [InlineKeyboardButton(text="🎁 Создать промокод", callback_data="admin_add_promo")],
        [InlineKeyboardButton(text="💳 Изменить баланс юзеру", callback_data="admin_edit_bal")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

@router.message(F.text == "/admin")
async def cmd_admin(message: Message, state: FSMContext):
    await clear_state(message, state)
    if message.from_user.id not in ADMIN_IDS:
        return
    text_tg = f'<tg-emoji id="{E_CROWN}">👑</tg-emoji> <b>Панель администратора:</b>'
    text_fb = f'👑 <b>Панель администратора:</b>'
    await safe_answer(message, text_tg, text_fb, parse_mode="HTML", reply_markup=get_admin_keyboard())

# ── АДМИН: ДОБАВЛЕНИЕ КАТЕГОРИИ ───────────────────────────────────────────────
@router.callback_query(F.data == "admin_add_cat")
async def admin_add_cat_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.message.answer("Укажите название новой категории:")
    await state.set_state(AddCategory.waiting_for_name)
    await callback.answer()

@router.message(AddCategory.waiting_for_name)
async def admin_add_cat_name(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    name = message.text.strip()
    async with AsyncSessionLocal() as session:
        new_cat = Category(name=name)
        session.add(new_cat)
        await session.commit()
    text_tg = f'<tg-emoji id="{E_CHECK}">✅</tg-emoji> Категория <b>{name}</b> успешно создана!'
    text_fb = f'✅ Категория <b>{name}</b> успешно создана!'
    await safe_answer(message, text_tg, text_fb, parse_mode="HTML")
    await state.clear()

# ── АДМИН: ДОБАВЛЕНИЕ ТОВАРА ──────────────────────────────────────────────────
@router.callback_query(F.data == "admin_add_prod")
async def admin_add_prod_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    async with AsyncSessionLocal() as session:
        cats = (await session.execute(select(Category))).scalars().all()
    if not cats:
        await callback.message.answer("Сначала создайте хотя бы одну категорию!")
        await callback.answer()
        return
    kb = [[InlineKeyboardButton(text=c.name, callback_data=f"ap_cat_{c.id}")] for c in cats]
    await callback.message.answer("Выберите категорию для товара:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await state.set_state(AddProduct.waiting_for_category)
    await callback.answer()

@router.callback_query(AddProduct.waiting_for_category, F.data.startswith("ap_cat_"))
async def admin_add_prod_cat_selected(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[2])
    await state.update_data(category_id=cat_id)
    await callback.message.answer("Введите название товара:")
    await state.set_state(AddProduct.waiting_for_name)
    await callback.answer()

@router.message(AddProduct.waiting_for_name)
async def admin_add_prod_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Введите описание товара:")
    await state.set_state(AddProduct.waiting_for_description)

@router.message(AddProduct.waiting_for_description)
async def admin_add_prod_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await message.answer("Укажите цену товара ($):")
    await state.set_state(AddProduct.waiting_for_price)

@router.message(AddProduct.waiting_for_price)
async def admin_add_prod_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(',', '.'))
    except ValueError:
        await message.answer("Введите корректное число.")
        return
    await state.update_data(price=price)
    await message.answer("Отправьте содержимое товара (текст/ссылки/логи):")
    await state.set_state(AddProduct.waiting_for_content)

@router.message(AddProduct.waiting_for_content)
async def admin_add_prod_content(message: Message, state: FSMContext):
    data = await state.get_data()
    content = message.text
    async with AsyncSessionLocal() as session:
        new_prod = Product(
            category_id=data['category_id'],
            name=data['name'],
            description=data['description'],
            price=data['price'],
            content=content,
            is_available=True
        )
        session.add(new_prod)
        await session.commit()
    text_tg = f'<tg-emoji id="{E_CHECK}">✅</tg-emoji> Товар <b>{data["name"]}</b> успешно добавлен в каталог!'
    text_fb = f'✅ Товар <b>{data["name"]}</b> успешно добавлен в каталог!'
    await safe_answer(message, text_tg, text_fb, parse_mode="HTML")
    await state.clear()

# ── АДМИН: СОЗДАНИЕ ПРОМОКОДА ─────────────────────────────────────────────────
@router.callback_query(F.data == "admin_add_promo")
async def admin_add_promo_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.message.answer("Введите имя промокода (код):")
    await state.set_state(AddPromo.waiting_for_code)
    await callback.answer()

@router.message(AddPromo.waiting_for_code)
async def admin_add_promo_code(message: Message, state: FSMContext):
    await state.update_data(code=message.text.strip())
    await message.answer("Укажите сумму бонуса ($):")
    await state.set_state(AddPromo.waiting_for_bonus)

@router.message(AddPromo.waiting_for_bonus)
async def admin_add_promo_bonus(message: Message, state: FSMContext):
    try:
        bonus = float(message.text.replace(',', '.'))
    except ValueError:
        await message.answer("Введите число.")
        return
    await state.update_data(bonus=bonus)
    await message.answer("Укажите макс. количество активаций (число) или 0 для бесконечности:")
    await state.set_state(AddPromo.waiting_for_max_act)

@router.message(AddPromo.waiting_for_max_act)
async def admin_add_promo_max(message: Message, state: FSMContext):
    try:
        max_act = int(message.text)
    except ValueError:
        await message.answer("Введите целое число.")
        return
    data = await state.get_data()
    max_act_val = None if max_act == 0 else max_act
    
    async with AsyncSessionLocal() as session:
        new_promo = Promocode(
            code=data['code'],
            bonus_amount=data['bonus'],
            max_activations=max_act_val,
            used_count=0,
            is_active=True
        )
        session.merge(new_promo)
        await session.commit()
        
    text_tg = f'<tg-emoji id="{E_GIFT}">🎁</tg-emoji> Промокод <code>{data["code"]}</code> на сумму <b>{data["bonus"]}$</b> успешно создан!'
    text_fb = f'🎁 Промокод <code>{data["code"]}</code> на сумму <b>{data["bonus"]}$</b> успешно создан!'
    await safe_answer(message, text_tg, text_fb, parse_mode="HTML")
    await state.clear()

# ── АДМИН: ИЗМЕНЕНИЕ БАЛАНСА ──────────────────────────────────────────────────
@router.callback_query(F.data == "admin_edit_bal")
async def admin_edit_bal_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.message.answer("Введите ID пользователя, которому нужно изменить баланс:")
    await state.set_state(AdminStates.waiting_for_user_id)
    await callback.answer()

@router.message(AdminStates.waiting_for_user_id)
async def admin_edit_bal_id(message: Message, state: FSMContext):
    try:
        uid = int(message.text)
    except ValueError:
        await message.answer("Неверный формат ID.")
        return
    await state.update_data(target_id=uid)
    await message.answer("Введите сумму (со знаком плюс для добавления, или минус для вычитания):")
    await state.set_state(AdminStates.waiting_for_balance_amount)

@router.message(AdminStates.waiting_for_balance_amount)
async def admin_edit_bal_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))
    except ValueError:
        await message.answer("Введите число.")
        return
    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        user = await session.get(User, data['target_id'])
        if not user:
            await message.answer("Пользователь не найден в базе данных.")
            await state.clear()
            return
        user.balance += amount
        await session.commit()
        new_bal = user.balance
        
    text_tg = f'<tg-emoji id="{E_CHECK}">✅</tg-emoji> Баланс пользователя <code>{data["target_id"]}</code> изменен на <b>{amount}$</b>. Новый баланс: <b>{new_bal:.2f}$</b>'
    text_fb = f'✅ Баланс пользователя <code>{data["target_id"]}</code> изменен на <b>{amount}$</b>. Новый баланс: <b>{new_bal:.2f}$</b>'
    await safe_answer(message, text_tg, text_fb, parse_mode="HTML")
    await state.clear()

# ── АДМИН: ОБЩАЯ РАССЫЛКА ПО БАЗЕ ───────────────────────────────────────────────
@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.message.answer("Отправьте текст рассылки (поддерживается HTML-разметка):")
    await state.set_state(AdminStates.waiting_for_broadcast_text)
    await callback.answer()

@router.message(AdminStates.waiting_for_broadcast_text)
async def admin_broadcast_process(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    text = message.text
    await message.answer("🚀 Рассылка запущена...")
    await state.clear()
    
    async with AsyncSessionLocal() as session:
        users = (await session.execute(select(User.user_id))).scalars().all()
        
    success = 0
    failed = 0
    for uid in users:
        try:
            await message.bot.send_message(uid, text, parse_mode="HTML")
            success += 1
            await asyncio.sleep(0.05) # Небольшой флуд-контроль
        except Exception:
            failed += 1
            
    text_tg = f'<tg-emoji id="{E_CHECK}">✅</tg-emoji> Рассылка завершена!\n\nУспешно: <b>{success}</b>\nОшибок: <b>{failed}</b>'
    text_fb = f'✅ Рассылка завершена!\n\nУспешно: <b>{success}</b>\nОшибок: <b>{failed}</b>'
    await safe_answer(message, text_tg, text_fb, parse_mode="HTML")

# ── АДМИН: ОБРАБОТКА ИНЛАЙН ЗАЯВОК НА ЗАМЕНУ И РАЗБЛОКИРОВКУ ───────────────────────
@router.callback_query(F.data.startswith("replace_approve_"))
async def admin_replace_approve(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    req_id = int(callback.data.split("_")[2])
    # Логика одобрения замены
    await callback.message.edit_reply_markup(reply_markup=None)
    await safe_answer(callback.message, f'<tg-emoji id="{E_CHECK}">✅</tg-emoji> Заявка #{req_id} одобрена.', f'✅ Заявка #{req_id} одобрена.', parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("replace_reject_"))
async def admin_replace_reject(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    req_id = int(callback.data.split("_")[2])
    # Логика отклонения замены
    await callback.message.edit_reply_markup(reply_markup=None)
    await safe_answer(callback.message, f'<tg-emoji id="{E_BAN}">🚫</tg-emoji> Заявка #{req_id} отклонена.', f'🚫 Заявка #{req_id} отклонена.', parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("unban_approve_"))
async def admin_unban_approve(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    req_id = int(callback.data.split("_")[2])
    async with AsyncSessionLocal() as session:
        req = await session.get(UnbanRequest, req_id)
        if req:
            user = await session.get(User, req.user_id)
            if user:
                user.is_banned = False
                await session.commit()
                try:
                    await callback.bot.send_message(req.user_id, f"🎉 Вы были успешно разблокированы администратором!")
                except Exception: pass
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Пользователь разблокирован", show_alert=True)

@router.callback_query(F.data.startswith("unban_reject_"))
async def admin_unban_reject(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    req_id = int(callback.data.split("_")[2])
    async with AsyncSessionLocal() as session:
        req = await session.get(UnbanRequest, req_id)
        if req:
            try:
                await callback.bot.send_message(req.user_id, f"🚫 Ваша заявка на разблокировку была отклонена.")
            except Exception: pass
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Заявка отклонена", show_alert=True)
