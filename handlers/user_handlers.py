from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from datetime import datetime
from database.database import AsyncSessionLocal
from database.models import User, Invoice, Promocode, Purchase
from keyboards.reply import main_menu
from keyboards.inline import categories_keyboard, products_keyboard, payment_keyboard
from services.user_service import get_user, create_user
from services.product_service import get_categories, get_products_by_category, buy_product
from services.replace_service import create_replace_request
from services.payment_service import create_invoice
from utils.states import ReplenishBalance, PromocodeInput, ReplaceRequestStates
from config import ADMIN_IDS

router = Router()

async def clear_state_on_menu(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await clear_state_on_menu(message, state)
    async with AsyncSessionLocal() as session:
        user = await get_user(session, message.from_user.id)
        if not user:
            await create_user(session, message.from_user.id, message.from_user.username)
            await message.answer("🎉 Вы зарегистрированы!", reply_markup=main_menu())
        else:
            await message.answer("С возвращением!", reply_markup=main_menu())

@router.message(F.text == "📋 Меню")
@router.message(F.text == "📦 Наличие товаров")
async def show_categories(message: Message, state: FSMContext):
    await clear_state_on_menu(message, state)
    async with AsyncSessionLocal() as session:
        categories = await get_categories(session, parent_id=None)
        if categories:
            await message.answer("Выберите категорию:", reply_markup=categories_keyboard(categories))
        else:
            await message.answer("Каталог временно пуст.")

@router.callback_query(F.data.startswith("cat_"))
async def category_selected(callback: CallbackQuery):
    cat_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        subcats = await get_categories(session, parent_id=cat_id)
        if subcats:
            await callback.message.edit_text("Выберите подкатегорию:", reply_markup=categories_keyboard(subcats))
        else:
            products = await get_products_by_category(session, cat_id)
            if products:
                await callback.message.edit_text("Доступные товары:", reply_markup=products_keyboard(products))
            else:
                await callback.answer("В этой категории пока нет товаров", show_alert=True)
    await callback.answer()

@router.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        categories = await get_categories(session, parent_id=None)
        if categories:
            await callback.message.edit_text("Категории:", reply_markup=categories_keyboard(categories))
        else:
            await callback.message.edit_text("Категорий нет")
    await callback.answer()

@router.callback_query(F.data.startswith("buy_"))
async def buy_product_handler(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    async with AsyncSessionLocal() as session:
        result = await buy_product(session, user_id, product_id)
        if result["success"]:
            text = f"✅ Покупка успешна!\nТовар: {result['product_name']}\nОстаток на балансе: {result['balance']:.2f}$"
            await callback.message.answer(text)
            if result.get("content"):
                await callback.message.answer(result["content"])
            if result.get("file_id"):
                try:
                    await callback.message.answer_document(result["file_id"])
                except:
                    await callback.message.answer("⚠️ Не удалось отправить файл, обратитесь в поддержку.")
        else:
            await callback.message.answer(f"❌ {result['error']}")
    await callback.answer()

@router.message(F.text == "👤 Профиль")
async def profile(message: Message, state: FSMContext):
    await clear_state_on_menu(message, state)
    async with AsyncSessionLocal() as session:
        user = await get_user(session, message.from_user.id)
        if not user:
            return
        days = (datetime.utcnow() - user.registered_at).days
        text = (
            f"👤 Ваш профиль:\n"
            f"Telegram ID: {user.user_id}\n"
            f"Username: @{user.username or 'нет'}\n"
            f"Баланс: {user.balance:.2f}$\n"
            f"Дата регистрации: {user.registered_at.strftime('%d.%m.%Y')}\n"
            f"Дней с регистрации: {days}"
        )
        await message.answer(text)

@router.message(F.text == "💳 Пополнить баланс")
async def ask_amount(message: Message, state: FSMContext):
    await clear_state_on_menu(message, state)
    await message.answer("Введите сумму пополнения в $:")
    await state.set_state(ReplenishBalance.amount)

@router.message(ReplenishBalance.amount)
async def process_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите положительное число.")
        return

    try:
        invoice_data = await create_invoice(amount, f"Пополнение баланса для {message.from_user.id}")
    except Exception as e:
        await message.answer(f"Ошибка при создании счёта: {e}")
        await state.clear()
        return

    pay_url = invoice_data["pay_url"]
    invoice_id = invoice_data["invoice_id"]

    async with AsyncSessionLocal() as session:
        inv = Invoice(user_id=message.from_user.id, invoice_id=invoice_id, amount=amount)
        session.add(inv)
        await session.commit()

    await message.answer(
        f"💳 Счёт на {amount}$ создан.\nОплатите по кнопке ниже и нажмите «Проверить оплату» после перевода.",
        reply_markup=payment_keyboard(pay_url)
    )
    await state.clear()

@router.callback_query(F.data == "check_payment")
async def check_payment(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(Invoice).where(Invoice.user_id == user_id, Invoice.status == 'active')
                .order_by(Invoice.created_at.desc()).limit(1)
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            await callback.answer("Нет активных счетов для проверки.", show_alert=True)
            return

        from services.payment_service import get_invoice
        data = await get_invoice(invoice.invoice_id)
        if data and data["status"] == "paid":
            invoice.status = "paid"
            user = await get_user(session, user_id)
            user.balance += invoice.amount
            await session.commit()
            await callback.message.answer(f"✅ Оплата получена! Ваш баланс пополнен на {invoice.amount:.2f}$.")
        elif data and data["status"] == "expired":
            invoice.status = "expired"
            await session.commit()
            await callback.message.answer("⌛ Срок действия счёта истёк. Создайте новый.")
        else:
            await callback.answer("Оплата ещё не поступила.", show_alert=True)
    await callback.answer()

@router.message(F.text == "🎁 Промокод")
async def ask_promocode(message: Message, state: FSMContext):
    await clear_state_on_menu(message, state)
    await message.answer("Введите промокод:")
    await state.set_state(PromocodeInput.code)

@router.message(PromocodeInput.code)
async def process_promocode(message: Message, state: FSMContext):
    code = message.text.strip()
    async with AsyncSessionLocal() as session:
        promocode = await session.get(Promocode, code)
        if not promocode or not promocode.is_active:
            await message.answer("❌ Промокод недействителен.")
        elif promocode.expires_at and promocode.expires_at < datetime.utcnow():
            await message.answer("❌ Срок действия промокода истёк.")
        elif promocode.max_activations and promocode.used_count >= promocode.max_activations:
            await message.answer("❌ Лимит активаций исчерпан.")
        else:
            user = await get_user(session, message.from_user.id)
            user.balance += promocode.bonus_amount
            promocode.used_count += 1
            await session.commit()
            await message.answer(f"🎁 Промокод активирован! Начислено {promocode.bonus_amount:.2f}$")
    await state.clear()

@router.message(F.text == "🔄 Замена")
async def start_replace(message: Message, state: FSMContext):
    await clear_state_on_menu(message, state)
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(Purchase).where(Purchase.user_id == message.from_user.id, Purchase.status == 'completed')
        )
        if not result.first():
            await message.answer("⚠️ У вас нет совершённых покупок для оформления замены.")
            return
    await message.answer("📱 Введите номер телефона:")
    await state.set_state(ReplaceRequestStates.phone_number)

@router.message(ReplaceRequestStates.phone_number)
async def get_phone(message: Message, state: FSMContext):
    await state.update_data(phone_number=message.text)
    await message.answer("📅 Введите дату и время операции (пример: 25.03.2025 14:30):")
    await state.set_state(ReplaceRequestStates.date_time)

@router.message(ReplaceRequestStates.date_time)
async def get_date_time(message: Message, state: FSMContext):
    data = await state.get_data()
    phone = data['phone_number']
    date_time = message.text

    async with AsyncSessionLocal() as session:
        try:
            req = await create_replace_request(session, message.from_user.id, phone, date_time)
        except ValueError as e:
            await message.answer(f"❌ {e}")
            await state.clear()
            return

        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_message(
                    admin_id,
                    f"🔄 Новая заявка на замену #{req.id}\n"
                    f"Пользователь: @{message.from_user.username} ({message.from_user.id})\n"
                    f"Телефон: {phone}\nДата/время: {date_time}",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_replace_{req.id}"),
                         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_replace_{req.id}")]
                    ])
                )
            except:
                pass
    await message.answer("✅ Заявка на замену отправлена. Ожидайте решение администратора.")
    await state.clear()
