from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from datetime import datetime
from database.database import AsyncSessionLocal
from database.models import User, Invoice, Promocode, Purchase, Product
from keyboards.reply import main_menu
from keyboards.inline import categories_keyboard, products_keyboard, payment_keyboard
from services.user_service import get_user, create_user
from services.product_service import get_categories, get_products_by_category, buy_product, get_all_products_text
from services.replace_service import create_replace_request
from services.payment_service import create_invoice
from utils.states import ReplenishBalance, PromocodeInput, ReplaceRequestStates, BuyProduct
from config import ADMIN_IDS

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

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await clear_state_on_menu(message, state)
    await ensure_user(message.from_user.id, message.from_user.username)
    await message.answer("🎉 Добро пожаловать!", reply_markup=main_menu())

@router.message(F.text == "📋 Меню")
async def show_categories(message: Message, state: FSMContext):
    await clear_state_on_menu(message, state)
    await ensure_user(message.from_user.id, message.from_user.username)
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session, parent_id=None)
        if cats:
            await message.answer("Выберите категорию:", reply_markup=categories_keyboard(cats))
        else:
            await message.answer("Каталог пуст. Добавьте категории через админку.")

@router.message(F.text == "📦 Наличие товаров")
async def show_all_products(message: Message, state: FSMContext):
    await clear_state_on_menu(message, state)
    await ensure_user(message.from_user.id, message.from_user.username)
    async with AsyncSessionLocal() as session:
        text = await get_all_products_text(session)
        await message.answer(text)

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
                    text += f"📌 {p.name}\n💰 Цена: {p.price}$ за шт.\n📦 В наличии: {p.quantity} шт.\n\n"
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

@router.callback_query(F.data.startswith("buy_"))
async def buy_start(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        product = await session.get(Product, product_id)
        if not product or not product.is_available:
            await callback.answer("Товар недоступен", show_alert=True)
            return
        desc = product.content if product.content else "Товар без текста"
        await callback.message.answer(
            f"📦 {product.name}\n💰 Цена: {product.price}$ за шт.\n📝 Товар:\n{desc}\n\n"
            f"Введите количество, которое хотите купить (доступно {product.quantity} шт.):"
        )
        await state.set_state(BuyProduct.amount)
        await state.update_data(product_id=product_id)
    await callback.answer()

@router.message(BuyProduct.amount)
async def buy_amount(message: Message, state: FSMContext):
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
            text = (f"✅ Куплено {amount} шт.\n"
                    f"Товар: {result['product_name']}\n"
                    f"Остаток: {result['balance']:.2f}$\n"
                    f"Осталось товара: {result['quantity_left']} шт.")
            await message.answer(text)
            if result.get("content"):
                await message.answer(f"📦 Ваш товар:\n{result['content']}")
            if result.get("file_id"):
                try:
                    await message.answer_document(result["file_id"])
                except:
                    pass
        else:
            await message.answer(f"❌ {result['error']}")
    await state.clear()

@router.message(F.text == "👤 Профиль")
async def profile(message: Message, state: FSMContext):
    await clear_state_on_menu(message, state)
    user = await ensure_user(message.from_user.id, message.from_user.username)
    days = (datetime.utcnow() - user.registered_at).days
    text = (f"👤 Профиль\n"
            f"ID: {user.user_id}\n"
            f"Username: @{user.username or 'нет'}\n"
            f"Баланс: {user.balance:.2f}$\n"
            f"Регистрация: {user.registered_at.strftime('%d.%m.%Y')} ({days} дн.)")
    await message.answer(text)

@router.message(F.text == "💳 Пополнить баланс")
async def ask_amount(message: Message, state: FSMContext):
    await clear_state_on_menu(message, state)
    await ensure_user(message.from_user.id, message.from_user.username)
    await message.answer("Введите сумму пополнения в $:")
    await state.set_state(ReplenishBalance.amount)

@router.message(ReplenishBalance.amount)
async def process_amount(message: Message, state: FSMContext):
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
        elif data and data['status'] == 'expired':
            inv.status = 'expired'
            await session.commit()
            await callback.message.answer("⌛ Счёт истёк.")
        else:
            await callback.answer("Оплата не поступила.", show_alert=True)
    await callback.answer()

@router.message(F.text == "🎁 Промокод")
async def promocode_start(message: Message, state: FSMContext):
    await clear_state_on_menu(message, state)
    await ensure_user(message.from_user.id, message.from_user.username)
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
    await state.clear()

@router.message(F.text == "🔄 Замена")
async def replace_start(message: Message, state: FSMContext):
    await clear_state_on_menu(message, state)
    user = await ensure_user(message.from_user.id, message.from_user.username)
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        exists = (await session.execute(
            select(Purchase).where(Purchase.user_id == message.from_user.id, Purchase.status == 'completed')
        )).first()
        if not exists:
            await message.answer("⚠️ Нет завершённых покупок.")
            return
    await message.answer("📱 Введите номер телефона:")
    await state.set_state(ReplaceRequestStates.phone_number)

@router.message(ReplaceRequestStates.phone_number)
async def replace_phone(message: Message, state: FSMContext):
    await state.update_data(phone_number=message.text)
    await message.answer("📅 Введите дату и время (пример: 25.03.2025 14:30):")
    await state.set_state(ReplaceRequestStates.date_time)

@router.message(ReplaceRequestStates.date_time)
async def replace_date(message: Message, state: FSMContext):
    data = await state.get_data()
    phone = data['phone_number']
    async with AsyncSessionLocal() as session:
        try:
            req = await create_replace_request(session, message.from_user.id, phone, message.text)
        except ValueError as e:
            await message.answer(f"❌ {e}")
            await state.clear()
            return
        if not ADMIN_IDS:
            await message.answer("❌ Администраторы не настроены.")
            await state.clear()
            return
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_message(admin_id,
                    f"🔄 Заявка на замену #{req.id}\nПользователь: @{message.from_user.username} ({message.from_user.id})\nТелефон: {phone}\nДата: {message.text}",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_replace_{req.id}"),
                         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_replace_{req.id}")]
                    ]))
            except Exception as e:
                print(f"Не удалось уведомить админа {admin_id}: {e}")
    await message.answer("✅ Заявка на замену отправлена.")
    await state.clear()
