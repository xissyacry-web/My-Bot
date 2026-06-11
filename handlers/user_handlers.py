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
from database.models import User, Invoice, Promocode, Purchase, Product, UnbanRequest, UserDiscount
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
from config import ADMIN_IDS, pe

router = Router()

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

# ── START ─────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await clear_state(message, state)
    async with AsyncSessionLocal() as session:
        user = await get_user(session, message.from_user.id)
        if not user:
            await create_user(session, message.from_user.id, message.from_user.username)
            await log_register(message.bot, message.from_user.id, message.from_user.username)
    await message.answer(
        f"{pe('crown')} <b>Добро пожаловать!</b>\n\nИспользуй меню ниже ↓",
        parse_mode="HTML",
        reply_markup=main_menu()
    )

# ── CATALOG ───────────────────────────────────────────────────────────────────

@router.message(F.text == "📋 Каталог")
async def show_categories(message: Message, state: FSMContext):
    await clear_state(message, state)
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session, parent_id=None)
    if cats:
        await message.answer(
            f"{pe('folder')} <b>Каталог</b>",
            parse_mode="HTML",
            reply_markup=categories_keyboard(cats)
        )
    else:
        await message.answer(f"{pe('box')} Каталог пуст", parse_mode="HTML")

@router.callback_query(F.data.startswith("cat_"))
async def category_selected(callback: CallbackQuery):
    cat_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        from database.models import Category
        cat = await session.get(Category, cat_id)
        if not cat:
            await callback.answer("Не найдено", show_alert=True)
            return
        subcats = await get_categories(session, parent_id=cat_id)
        if subcats:
            await callback.message.edit_text(
                f"{pe('folder')} <b>{cat.name}</b>",
                parse_mode="HTML",
                reply_markup=categories_keyboard(subcats)
            )
        else:
            products = await get_products_by_category(session, cat_id)
            if products:
                await callback.message.edit_text(
                    f"{pe('folder')} <b>{cat.name}</b>\n\nВыбери товар:",
                    parse_mode="HTML",
                    reply_markup=products_keyboard(products)
                )
            else:
                await callback.answer("Товаров нет", show_alert=True)
    await callback.answer()

@router.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session, parent_id=None)
    if cats:
        await callback.message.edit_text(
            f"{pe('folder')} <b>Каталог</b>",
            parse_mode="HTML",
            reply_markup=categories_keyboard(cats)
        )
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

        text = (
            f"{pe('box')} <b>{product.name}</b>\n\n"
            f"{product.description or 'Описание отсутствует'}\n\n"
            f"{price_line}\n"
            f"{pe('clock')} В наличии: {qty} шт.\n\n"
            f"Введите количество:"
        )
    await callback.message.answer(text, parse_mode="HTML")
    await state.set_state(BuyProduct.amount)
    await state.update_data(product_id=product_id)
    await callback.answer()

@router.message(BuyProduct.amount)
async def buy_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount <= 0:
            raise ValueError
    except Exception:
        await message.answer("Введите целое положительное число.")
        return

    data = await state.get_data()
    product_id = data['product_id']
    user_id = message.from_user.id
    await ensure_user(user_id, message.from_user.username)

    async with AsyncSessionLocal() as session:
        disc = await get_active_discount(session, user_id)
        discount_pct = disc.percent if disc else 0
        result = await buy_product(session, user_id, product_id, amount, discount_pct)

        if result["success"]:
            qleft = result.get('quantity_left', 0)
            qleft_str = f"{qleft} шт." if isinstance(qleft, int) and qleft > 0 else "∞"
            text = (
                f"{pe('check')} <b>Куплено {amount} шт.</b>\n"
                f"{pe('wallet')} Итого: {result.get('total_price', 0):.2f}$\n"
                f"Баланс: {result['balance']:.2f}$\n"
                f"{pe('box')} Осталось: {qleft_str}"
            )
            await message.answer(text, parse_mode="HTML")

            if result.get("content"):
                await message.answer(
                    f"{pe('books')} <b>Ваш товар:</b>\n\n<code>{result['content']}</code>",
                    parse_mode="HTML"
                )
            if result.get("file_id"):
                try:
                    await message.answer_document(result["file_id"])
                except Exception:
                    pass

            # Лог в канал с номерами строк
            await log_purchase(
                message.bot, user_id, message.from_user.username,
                result['product_name'], amount, result.get('total_price', 0),
                lines=result.get('selected_lines', [])
            )
        else:
            await message.answer(f"{pe('warning')} {result['error']}", parse_mode="HTML")

    await state.clear()

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
    disc_line = ""
    if disc:
        left = disc.expires_at - datetime.utcnow()
        h = int(left.total_seconds() // 3600)
        disc_line = f"\n{pe('star')} Скидка: <b>{disc.percent}%</b> (ещё {h}ч.)"

    text = (
        f"{pe('user')} <b>Профиль</b>\n\n"
        f"ID: <code>{user.user_id}</code>\n"
        f"Username: @{user.username or '—'}\n"
        f"{pe('wallet')} Баланс: <b>{user.balance:.2f}$</b>\n"
        f"{pe('briefcase')} Покупок: {purchases_count}\n"
        f"{pe('clock')} Дней с нами: {days}"
        f"{disc_line}"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=profile_keyboard())

@router.callback_query(F.data == "profile_back")
async def profile_back(callback: CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=profile_keyboard())
    await callback.answer()

# ── TOPUP ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "profile_topup")
async def profile_topup(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(f"{pe('wallet')} Введите сумму пополнения ($):", parse_mode="HTML")
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
    await message.answer(
        f"{pe('wallet')} Счёт на <b>{amount}$</b> создан.\nОплатите и нажмите «Проверить».",
        parse_mode="HTML",
        reply_markup=payment_keyboard(inv['pay_url'])
    )
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
            await callback.message.answer(
                f"{pe('check')} Зачислено <b>{inv.amount:.2f}$</b>",
                parse_mode="HTML"
            )
            await log_refill(callback.bot, user_id, callback.from_user.username, inv.amount)
        elif data and data['status'] == 'expired':
            inv.status = 'expired'
            await session.commit()
            await callback.message.answer(f"{pe('clock')} Счёт истёк.", parse_mode="HTML")
        else:
            await callback.answer("Оплата не поступила.", show_alert=True)
    await callback.answer()

# ── PROMO ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "profile_promo")
async def promo_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(f"{pe('gift')} Введите промокод:", parse_mode="HTML")
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
            await message.answer(f"{pe('ban')} Уже использован.", parse_mode="HTML")
        elif not promo or not promo.is_active:
            await message.answer(f"{pe('ban')} Недействителен.", parse_mode="HTML")
        elif promo.expires_at and promo.expires_at < datetime.utcnow():
            await message.answer(f"{pe('clock')} Истёк.", parse_mode="HTML")
        elif promo.max_activations is not None and promo.used_count >= promo.max_activations:
            await message.answer(f"{pe('ban')} Лимит исчерпан.", parse_mode="HTML")
        else:
            user.balance += promo.bonus_amount
            promo.used_count += 1
            used.append(code)
            user.used_promocodes = ','.join(used)
            await session.commit()
            await message.answer(
                f"{pe('gift')} <b>+{promo.bonus_amount:.2f}$</b> на баланс!",
                parse_mode="HTML"
            )
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
    await callback.message.edit_text(
        f"{pe('books')} <b>Покупки</b> — выбери для деталей:",
        parse_mode="HTML",
        reply_markup=history_keyboard(purchases)
    )
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

    text = (
        f"{pe('box')} <b>{pname}</b>\n"
        f"Кол-во: {p.amount} шт.\n"
        f"{pe('wallet')} {p.price:.2f}$\n"
        f"{pe('clock')} {p.purchased_at.strftime('%d.%m.%Y %H:%M')}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад", callback_data="profile_history")
    ]])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

# ── DISCOUNT ──────────────────────────────────────────────────────────────────

@router.message(F.text == "🏷 Скидка")
async def spin_discount(message: Message, state: FSMContext):
    await clear_state(message, state)
    user_id = message.from_user.id
    async with AsyncSessionLocal() as session:
        existing = await get_active_discount(session, user_id)
        if existing:
            left = existing.expires_at - datetime.utcnow()
            h = int(left.total_seconds() // 3600)
            await message.answer(
                f"{pe('star')} У тебя уже есть скидка <b>{existing.percent}%</b>\n"
                f"{pe('clock')} Действует ещё {h} ч.",
                parse_mode="HTML"
            )
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

    await message.answer(
        f"{pe('star')} Тебе выпала скидка <b>{percent}%</b> на 24 часа!\n\n"
        f"{pe('check')} Применяется автоматически при покупке.",
        parse_mode="HTML"
    )

# ── SUPPORT ───────────────────────────────────────────────────────────────────

@router.message(F.text == "🆘 Поддержка")
async def support(message: Message, state: FSMContext):
    await clear_state(message, state)
    await message.answer(
        f"{pe('info')} Поддержка: @XissyaSup",
        parse_mode="HTML"
    )

# ── REPLACE ───────────────────────────────────────────────────────────────────

@router.message(F.text == "♻️ Замена")
async def replace_start(message: Message, state: FSMContext):
    await clear_state(message, state)
    async with AsyncSessionLocal() as session:
        exists = (await session.execute(
            select(Purchase).where(Purchase.user_id == message.from_user.id, Purchase.status == 'completed')
        )).first()
        if not exists:
            await message.answer(f"{pe('warning')} Нет завершённых покупок.", parse_mode="HTML")
            return
    await message.answer(f"{pe('hammer')} Укажи номер лога и время покупки:", parse_mode="HTML")
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
            await message.answer(f"{pe('warning')} {e}", parse_mode="HTML")
            await state.clear()
            return
        for admin_id in ADMIN_IDS:
            try:
                caption = (
                    f"{pe('hammer')} Заявка на замену #{req.id}\n"
                    f"{pe('user')} @{message.from_user.username} ({message.from_user.id})\n"
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
    await message.answer(f"{pe('check')} Заявка отправлена.", parse_mode="HTML")
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
        from database.models import UnbanRequest
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
                    f"{pe('unlock')} Разблокировка #{req.id}\n"
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
    await callback.message.answer(f"{pe('check')} Заявка отправлена.", parse_mode="HTML")
    await state.clear()

@router.callback_query(UnbanProcess.confirm, F.data == "unban_cancel")
async def unban_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Отменено.")
    await state.clear()

@router.callback_query(F.data == "unban_ignore")
async def unban_ignore(callback: CallbackQuery):
    await callback.answer()
