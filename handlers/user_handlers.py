from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from datetime import datetime
from database.database import AsyncSessionLocal
from database.models import User, Invoice, Promocode, Purchase, Product, ReplaceRequest, UnbanRequest
from keyboards.reply import main_menu
from keyboards.inline import categories_keyboard, products_keyboard, payment_keyboard
from services.user_service import get_user, create_user
from services.product_service import get_categories, get_products_by_category, buy_product, get_all_products_text

from services.payment_service import create_invoice
from services.log_service import log_purchase, log_register, log_refill, log_promo, log_replace
from utils.states import ReplenishBalance, PromocodeInput, ReplaceRequestStates, BuyProduct, UnbanProcess
from config import ADMIN_IDS, BOT_ACTIVE, TECH_MODE

router = Router()

async def ensure_user(user_id: int, username: str = None):
    async with AsyncSessionLocal() as session:
        user = await get_user(session, user_id)
        if not user:
            user = await create_user(session, user_id, username)
        return user

async def clear_state_on_menu(message: Message, state: FSMContext):
    current = await state.get_state()
    if current is not None:
        await state.clear()

async def check_bot_active(message: Message):
    if not BOT_ACTIVE and message.from_user.id not in ADMIN_IDS:
        await message.answer("🔴 Бот отключён.")
        return False
    if TECH_MODE and message.from_user.id not in ADMIN_IDS:
        await message.answer("🔴 Бот временно отключён для тех. работ.")
        return False
    return True

# ---------- /start ----------
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await clear_state_on_menu(message, state)
    if not await check_bot_active(message): return
    async with AsyncSessionLocal() as session:
        user = await get_user(session, message.from_user.id)
        if not user:
            await create_user(session, message.from_user.id, message.from_user.username)
            await log_register(message.bot, message.from_user.id, message.from_user.username)
    await message.answer("🎉 Добро пожаловать!", reply_markup=main_menu())

# ---------- МЕНЮ ----------
@router.message(F.text == "📋 Меню")
async def show_categories(message: Message, state: FSMContext):
    await clear_state_on_menu(message, state)
    if not await check_bot_active(message): return
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session, parent_id=None)
        if cats:
            await message.answer("Выберите категорию:", reply_markup=categories_keyboard(cats))
        else:
            await message.answer("В каталоге пока нет товаров.")

@router.message(F.text == "📦 Наличие товаров")
async def show_all_products(message: Message, state: FSMContext):
    await clear_state_on_menu(message, state)
    if not await check_bot_active(message): return
    async with AsyncSessionLocal() as session:
        text = await get_all_products_text(session)
        await message.answer(text)

# ---------- КАТЕГОРИИ ----------
@router.callback_query(F.data.startswith("cat_"))
async def category_selected(callback: CallbackQuery):
    cat_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        from database.models import Category
        cat = await session.get(Category, cat_id)
        if not cat:
            await callback.answer("Категория не найдена", show_alert=True)
            return

        subcats = await get_categories(session, parent_id=cat_id)
        if subcats:
            await callback.message.edit_text("Выберите подкатегорию:", reply_markup=categories_keyboard(subcats))
        else:
            products = await get_products_by_category(session, cat_id)
            if products:
                text = "Доступные товары:\n\n"
                for p in products:
                    qty = "∞" if p.quantity == 0 else str(p.quantity)
                    desc = p.description if p.description else "без описания"
                    text += f"📌 {p.name}\n💰 Цена: {p.price}$ за шт.\n📦 В наличии: {qty} шт.\n📝 {desc}\n\n"
                await callback.message.edit_text(text, reply_markup=products_keyboard(products))
            else:
                await callback.answer("В этой категории пока нет товаров", show_alert=True)
    await callback.answer()

@router.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session, parent_id=None)
        if cats:
            await callback.message.edit_text("Категории:", reply_markup=categories_keyboard(cats))
        else:
            await callback.message.edit_text("Категорий нет")
    await callback.answer()

# ---------- ПОКУПКА ----------
@router.callback_query(F.data.startswith("buy_"))
async def buy_start(callback: CallbackQuery, state: FSMContext):
    if not BOT_ACTIVE and callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Бот отключён", show_alert=True); return
    if TECH_MODE and callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Тех. работы", show_alert=True); return
    product_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        product = await session.get(Product, product_id)
        if not product or not product.is_available:
            await callback.answer("Товар недоступен", show_alert=True)
            return
        qty = "∞" if product.quantity == 0 else str(product.quantity)
        desc = product.description if product.description else "Описание отсутствует"
        await callback.message.answer(
            f"📦 {product.name}\n💰 Цена: {product.price}$ за шт.\n📝 {desc}\n\n"
            f"Введите количество, которое хотите купить (доступно {qty} шт.):"
        )
        await state.set_state(BuyProduct.amount)
        await state.update_data(product_id=product_id)
    await callback.answer()

@router.message(BuyProduct.amount)
async def buy_amount(message: Message, state: FSMContext):
    if not await check_bot_active(message): return
    try:
        amount = int(message.text)
        if amount <= 0:
            raise ValueError
    except:
        await message.answer("Введите положительное целое число.")
        return

    data = await state.get_data()
    product_id = data['product_id']
    user_id = message.from_user.id
    await ensure_user(user_id, message.from_user.username)

    async with AsyncSessionLocal() as session:
        result = await buy_product(session, user_id, product_id, amount)
        if result["success"]:
            qleft = result.get('quantity_left', 0)
            qleft_str = f"{qleft} шт." if isinstance(qleft, int) and qleft > 0 else ("∞" if qleft == 0 else qleft)
            text = (f"✅ Куплено {amount} шт.\n"
                    f"Товар: {result['product_name']}\n"
                    f"Остаток: {result['balance']:.2f}$\n"
                    f"Осталось товара: {qleft_str}")
            await message.answer(text)
            if result.get("content"):
                await message.answer(f"📦 Ваш товар:\n{result['content']}")
            if result.get("file_id"):
                try:
                    await message.answer_document(result["file_id"])
                except:
                    pass
            await log_purchase(message.bot, user_id, message.from_user.username, result['product_name'], amount, result.get('price', 0))
        else:
            await message.answer(f"❌ {result['error']}")
    await state.clear()

# ---------- ПРОФИЛЬ ----------
@router.message(F.text == "👤 Профиль")
async def profile(message: Message, state: FSMContext):
    await clear_state_on_menu(message, state)
    if not await check_bot_active(message): return
    user = await ensure_user(message.from_user.id, message.from_user.username)
    days = (datetime.utcnow() - user.registered_at).days
    text = (f"👤 Профиль\n"
            f"ID: {user.user_id}\n"
            f"Username: @{user.username or 'нет'}\n"
            f"Баланс: {user.balance:.2f}$\n"
            f"Регистрация: {user.registered_at.strftime('%d.%m.%Y')} ({days} дн.)")
    await message.answer(text)

# ---------- ПОПОЛНЕНИЕ ----------
@router.message(F.text == "💳 Пополнить баланс")
async def ask_amount(message: Message, state: FSMContext):
    await clear_state_on_menu(message, state)
    if not await check_bot_active(message): return
    await message.answer("Введите сумму пополнения в $:")
    await state.set_state(ReplenishBalance.amount)

@router.message(ReplenishBalance.amount)
async def process_amount(message: Message, state: FSMContext):
    if not await check_bot_active(message): return
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError
    except:
        await message.answer("Введите положительное число.")
        return
    try:
        inv = await create_invoice(amount, f"Пополнение {message.from_user.id}")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
        await state.clear()
        return
    async with AsyncSessionLocal() as session:
        invoice = Invoice(user_id=message.from_user.id, invoice_id=inv['invoice_id'], amount=amount)
        session.add(invoice)
        await session.commit()
    await message.answer(f"💳 Счёт на {amount}$ создан.\nОплатите и нажмите «Проверить оплату».",
                         reply_markup=payment_keyboard(inv['pay_url']))
    await state.clear()

@router.callback_query(F.data == "check_payment")
async def check_payment(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        inv = (await session.execute(select(Invoice).where(Invoice.user_id == user_id, Invoice.status == 'active')
                                     .order_by(Invoice.created_at.desc()).limit(1))).scalar_one_or_none()
        if not inv:
            await callback.answer("Нет активных счетов.", show_alert=True)
            return
        from services.payment_service import get_invoice
        data = await get_invoice(inv.invoice_id)
        if data and data['status'] == 'paid':
            inv.status = 'paid'
            user = await get_user(session, user_id)
            user.balance += inv.amount
            await session.commit()
            await callback.message.answer(f"✅ Зачислено {inv.amount:.2f}$")
            await log_refill(callback.bot, user_id, callback.from_user.username, inv.amount)
        elif data and data['status'] == 'expired':
            inv.status = 'expired'
            await session.commit()
            await callback.message.answer("⌛ Счёт истёк.")
        else:
            await callback.answer("Оплата не поступила.", show_alert=True)
    await callback.answer()

# ---------- ПРОМОКОДЫ ----------
@router.message(F.text == "🎁 Промокод")
async def promocode_start(message: Message, state: FSMContext):
    await clear_state_on_menu(message, state)
    if not await check_bot_active(message): return
    await message.answer("Введите промокод:")
    await state.set_state(PromocodeInput.code)

@router.message(PromocodeInput.code)
async def promocode_apply(message: Message, state: FSMContext):
    code = message.text.strip()
    user_id = message.from_user.id
    async with AsyncSessionLocal() as session:
        user = await get_user(session, user_id)
        if not user:
            await message.answer("Сначала нажмите /start")
            await state.clear()
            return
        promo = await session.get(Promocode, code)
        used = [c.strip() for c in user.used_promocodes.split(',') if c.strip()]
        if code in used:
            await message.answer("❌ Вы уже использовали этот промокод.")
            await state.clear()
            return
        if not promo or not promo.is_active:
            await message.answer("❌ Промокод недействителен.")
        elif promo.expires_at and promo.expires_at < datetime.utcnow():
            await message.answer("❌ Истёк срок действия.")
        elif promo.max_activations is not None and promo.used_count >= promo.max_activations:
            await message.answer("❌ Лимит активаций исчерпан.")
        else:
            user.balance += promo.bonus_amount
            promo.used_count += 1
            used.append(code)
            user.used_promocodes = ','.join(used)
            await session.commit()
            await message.answer(f"🎁 Промокод активирован! +{promo.bonus_amount:.2f}$")
            await log_promo(message.bot, user_id, message.from_user.username, code, promo.bonus_amount)
    await state.clear()

# ---------- ЗАМЕНА (ПОЛНОСТЬЮ РАБОЧАЯ) ----------
@router.message(F.text == "🔄 Замена")
async def replace_start(message: Message, state: FSMContext):
    await clear_state_on_menu(message, state)
    if not await check_bot_active(message): return
    async with AsyncSessionLocal() as session:
        exists = (await session.execute(
            select(Purchase).where(Purchase.user_id == message.from_user.id, Purchase.status == 'completed')
        )).first()
        if not exists:
            await message.answer("⚠️ Нет завершённых покупок.")
            return
    await message.answer("Введите номер телефона:")
    await state.set_state(ReplaceRequestStates.phone_number)

@router.message(ReplaceRequestStates.phone_number)
async def replace_phone(message: Message, state: FSMContext):
    await state.update_data(phone_number=message.text)
    await message.answer("Введите дату и время операции (пример: 25.03.2025 14:30):")
    await state.set_state(ReplaceRequestStates.date_time)

@router.message(ReplaceRequestStates.date_time)
async def replace_date(message: Message, state: FSMContext):
    await state.update_data(date_time=message.text)
    await message.answer("Теперь отправляйте фото по одному. Когда закончите, напишите 'готово'.")
    await state.set_state(ReplaceRequestStates.photos)
    await state.update_data(photos=[])

@router.message(ReplaceRequestStates.photos, F.photo)
async def replace_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get('photos', [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(f"Фото {len(photos)} получено. Отправьте ещё или напишите 'готово'.")

@router.message(ReplaceRequestStates.photos, F.text)
async def replace_photos_text_handler(message: Message, state: FSMContext):
    if message.text.strip().lower() == "готово":
        data = await state.get_data()
        photos = data.get('photos', [])
        if not photos:
            await message.answer("Вы не отправили ни одного фото. Отправьте фото или напишите '-', если их нет.")
            return
        await state.update_data(photos=photos)
        await message.answer("Опишите вашу жалобу текстом:")
        await state.set_state(ReplaceRequestStates.complaint)
    else:
        await message.answer("Отправьте фото или напишите 'готово' для завершения.")

@router.message(ReplaceRequestStates.complaint)
async def replace_complaint(message: Message, state: FSMContext):
    complaint = message.text
    data = await state.get_data()
    phone = data['phone_number']
    date_time = data['date_time']
    photos = data.get('photos', [])

    async with AsyncSessionLocal() as session:
        try:
            req = await create_replace_request(session, message.from_user.id, phone, date_time, photos, complaint)
        except ValueError as e:
            await message.answer(f"❌ {e}")
            await state.clear()
            return

        for admin_id in ADMIN_IDS:
            try:
                text_msg = (f"🔄 Заявка на замену #{req.id}\n"
                            f"Пользователь: @{message.from_user.username} ({message.from_user.id})\n"
                            f"Телефон: {phone}\nДата: {date_time}\n"
                            f"Жалоба: {complaint}")
                if photos:
                    media = [InputMediaPhoto(media=pid) for pid in photos]
                    await message.bot.send_media_group(admin_id, media)
                await message.bot.send_message(admin_id, text_msg,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_replace_{req.id}"),
                         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_replace_{req.id}")]
                    ]))
            except Exception as e:
                print(f"Ошибка уведомления админа: {e}")
    await message.answer("✅ Заявка на замену отправлена. Ожидайте решения администратора.")
    await state.clear()

# ---------- ПОДДЕРЖКА ----------
@router.message(F.text == "🆘 Поддержка")
async def support(message: Message, state: FSMContext):
    await clear_state_on_menu(message, state)
    await message.answer("Свяжитесь с поддержкой: @Xissya")

# ---------- РАЗЖАЛОВАНИЕ (UNBAN REQUEST) ----------
@router.callback_query(F.data == "unban_request")
async def unban_request(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if not user or not user.is_banned:
            await callback.answer("Вы не заблокированы!", show_alert=True)
            return
    await callback.message.answer("Начинаем процесс разжалования.\nОтправьте фото (по одному). Если фото нет, напишите '-'")
    await state.set_state(UnbanProcess.waiting_photos)
    await state.update_data(photos=[])
    await callback.answer()

@router.message(UnbanProcess.waiting_photos, F.photo)
async def unban_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get('photos', [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(f"Фото {len(photos)} получено. Отправьте ещё или напишите 'готово'.")

@router.message(UnbanProcess.waiting_photos, F.text)
async def unban_photo_text(message: Message, state: FSMContext):
    if message.text.strip().lower() == "готово":
        data = await state.get_data()
        photos = data.get('photos', [])
        if not photos:
            await message.answer("Вы не отправили ни одного фото. Отправьте фото или напишите '-' (если фото нет).")
            return
        await state.update_data(photos=photos)
        await message.answer("Сколько фото вы отправили (для проверки)? Напишите число или 'готово', если всё верно.")
        await state.set_state(UnbanProcess.waiting_done)
    elif message.text.strip() == "-":
        await state.update_data(photos=[])
        await message.answer("Фото не приложены. Теперь опишите вашу жалобу текстом:")
        await state.set_state(UnbanProcess.waiting_description)
    else:
        await message.answer("Отправьте фото или напишите 'готово'.")

@router.message(UnbanProcess.waiting_done)
async def unban_count(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get('photos', [])
    if message.text.strip().lower() == "готово":
        await message.answer(f"Принято {len(photos)} фото. Теперь опишите вашу жалобу текстом:")
        await state.set_state(UnbanProcess.waiting_description)
    else:
        try:
            count = int(message.text)
            if count != len(photos):
                await message.answer(f"Вы отправили {len(photos)} фото, а указали {count}. Отправьте ещё фото или напишите 'готово' ещё раз.")
                return
            await message.answer(f"Верно, {count} фото. Теперь опишите вашу жалобу текстом:")
            await state.set_state(UnbanProcess.waiting_description)
        except:
            await message.answer("Введите число или 'готово'.")

@router.message(UnbanProcess.waiting_description)
async def unban_description(message: Message, state: FSMContext):
    description = message.text
    await state.update_data(description=description)
    await message.answer("Проверьте ваши данные. Отправить разжалование?",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="Отправить", callback_data="unban_confirm"),
                              InlineKeyboardButton(text="Отмена", callback_data="unban_cancel")]
                         ]))
    await state.set_state(UnbanProcess.confirm)

@router.callback_query(UnbanProcess.confirm, F.data == "unban_confirm")
async def unban_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    photos = data.get('photos', [])
    description = data.get('description', '-')
    user_id = callback.from_user.id

    async with AsyncSessionLocal() as session:
        req = UnbanRequest(
            user_id=user_id,
            photos=','.join(photos) if photos else None,
            description=description
        )
        session.add(req)
        await session.commit()
        for admin_id in ADMIN_IDS:
            try:
                if photos:
                    media = [InputMediaPhoto(media=pid) for pid in photos]
                    await callback.bot.send_media_group(admin_id, media)
                await callback.bot.send_message(admin_id,
                    f"🔓 Заявка на разжалование #{req.id}\n"
                    f"Пользователь: @{callback.from_user.username} ({user_id})\n"
                    f"Жалоба: {description}",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"unban_approve_{req.id}"),
                         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"unban_reject_{req.id}")]
                    ]))
            except Exception as e:
                print(f"Ошибка уведомления админа: {e}")
    await callback.message.answer("Заявка на разжалование отправлена администратору.")
    await state.clear()

@router.callback_query(UnbanProcess.confirm, F.data == "unban_cancel")
async def unban_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Разжалование отменено.")
    await state.clear()

@router.callback_query(F.data == "unban_ignore")
async def unban_ignore(callback: CallbackQuery):
    await callback.answer("Ок")
