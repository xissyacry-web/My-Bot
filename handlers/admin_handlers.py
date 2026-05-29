from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.database import AsyncSessionLocal
from database.models import User, Product, Category, ReplaceRequest, Purchase
from config import ADMIN_IDS
from utils.states import AdminAddProduct, AdminEditProduct, AdminManageUser
from services.payment_service import get_invoice

router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# ========== Главное админ-меню ==========
@router.message(F.text == "/admin")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "🛠 Админ-панель:\n"
        "/add_product — добавить товар\n"
        "/products — список товаров\n"
        "/ban <user_id> — заблокировать\n"
        "/unban <user_id> — разблокировать\n"
        "/set_balance <user_id> <сумма> — изменить баланс\n"
        "/replaces — активные заявки на замену"
    )

# ========== Управление товарами ==========
@router.message(F.text == "/add_product")
async def start_add_product(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await message.answer("Введите ID категории (или /categories для просмотра):")
    await state.set_state(AdminAddProduct.category_id)

@router.message(AdminAddProduct.category_id)
async def process_cat(message: Message, state: FSMContext):
    if message.text == "/categories":
        async with AsyncSessionLocal() as session:
            cats = (await session.execute(
                Category.__table__.select().where(Category.is_active == True)
            )).fetchall()
            if cats:
                text = "\n".join(f"{c.id}: {c.name}" for c in cats)
            else:
                text = "Категорий нет"
        await message.answer(text)
        return
    try:
        cat_id = int(message.text)
    except:
        await message.answer("Введите число")
        return
    await state.update_data(category_id=cat_id)
    await message.answer("Введите название товара:")
    await state.set_state(AdminAddProduct.name)

@router.message(AdminAddProduct.name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите цену:")
    await state.set_state(AdminAddProduct.price)

@router.message(AdminAddProduct.price)
async def process_price(message: Message, state: FSMContext):
    try:
        price = float(message.text)
    except:
        await message.answer("Введите число")
        return
    await state.update_data(price=price)
    await message.answer("Отправьте файл товара (документ или фото):")
    await state.set_state(AdminAddProduct.file)

@router.message(AdminAddProduct.file, F.document | F.photo)
async def process_file(message: Message, state: FSMContext):
    data = await state.get_data()
    file_id = message.document.file_id if message.document else message.photo[-1].file_id

    async with AsyncSessionLocal() as session:
        product = Product(
            category_id=data['category_id'],
            name=data['name'],
            price=data['price'],
            file_id=file_id
        )
        session.add(product)
        await session.commit()
    await message.answer("✅ Товар добавлен!")
    await state.clear()

# ========== Управление пользователями ==========
@router.message(F.text.startswith("/ban"))
async def ban_user(message: Message):
    if not is_admin(message.from_user.id): return
    try:
        uid = int(message.text.split()[1])
    except:
        await message.answer("Формат: /ban <user_id>")
        return
    async with AsyncSessionLocal() as session:
        user = await session.get(User, uid)
        if user:
            user.is_banned = True
            await session.commit()
            await message.answer(f"Пользователь {uid} заблокирован.")
        else:
            await message.answer("Пользователь не найден.")

@router.message(F.text.startswith("/unban"))
async def unban_user(message: Message):
    if not is_admin(message.from_user.id): return
    try:
        uid = int(message.text.split()[1])
    except:
        await message.answer("Формат: /unban <user_id>")
        return
    async with AsyncSessionLocal() as session:
        user = await session.get(User, uid)
        if user:
            user.is_banned = False
            await session.commit()
            await message.answer(f"Пользователь {uid} разблокирован.")
        else:
            await message.answer("Пользователь не найден.")

@router.message(F.text.startswith("/set_balance"))
async def set_balance(message: Message):
    if not is_admin(message.from_user.id): return
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Формат: /set_balance <user_id> <сумма>")
        return
    try:
        uid = int(parts[1])
        amount = float(parts[2])
    except:
        await message.answer("Неверные данные")
        return
    async with AsyncSessionLocal() as session:
        user = await session.get(User, uid)
        if user:
            user.balance += amount
            await session.commit()
            await message.answer(f"Баланс пользователя {uid} изменён на {amount}. Текущий: {user.balance:.2f}")
        else:
            await message.answer("Пользователь не найден.")

# ========== Обработка заявок на замену ==========
@router.callback_query(F.data.startswith("approve_replace_"))
async def approve_replace(callback: CallbackQuery):
    req_id = int(callback.data.split("_")[2])
    async with AsyncSessionLocal() as session:
        req = await session.get(ReplaceRequest, req_id)
        if not req or req.status != "pending":
            await callback.answer("Заявка уже обработана")
            return
        req.status = "approved"
        # Отправляем файл из связанной покупки
        purchase = await session.get(Purchase, req.purchase_id)
        product = await session.get(Product, purchase.product_id) if purchase else None
        await session.commit()
        try:
            await callback.bot.send_message(
                req.user_id,
                f"✅ Ваша заявка на замену #{req.id} одобрена. Файл отправляется:"
            )
            if product and product.file_id:
                await callback.bot.send_document(req.user_id, product.file_id)
            else:
                await callback.bot.send_message(req.user_id, "Файл не найден, обратитесь в поддержку.")
        except Exception as e:
            await callback.answer(f"Ошибка отправки: {e}")
    await callback.message.edit_reply_markup()  # убираем кнопки
    await callback.answer("Заявка одобрена")

@router.callback_query(F.data.startswith("reject_replace_"))
async def reject_replace(callback: CallbackQuery, state: FSMContext):
    req_id = int(callback.data.split("_")[2])
    await callback.message.answer("Введите причину отказа:")
    await state.set_state(AdminManageUser.action)
    await state.update_data(req_id=req_id, admin_msg=callback.message.message_id, chat_id=callback.message.chat.id)
    await callback.answer()

@router.message(AdminManageUser.action)
async def process_reject_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    req_id = data['req_id']
    reason = message.text
    async with AsyncSessionLocal() as session:
        req = await session.get(ReplaceRequest, req_id)
        if req and req.status == "pending":
            req.status = "rejected"
            req.admin_comment = reason
            await session.commit()
            try:
                await message.bot.send_message(
                    req.user_id,
                    f"❌ Ваша заявка на замену #{req.id} отклонена.\nПричина: {reason}"
                )
                await message.answer("Отказ отправлен пользователю.")
            except:
                await message.answer("Не удалось уведомить пользователя.")
        else:
            await message.answer("Заявка уже обработана.")
    await state.clear()

@router.message(F.text == "/replaces")
async def list_replaces(message: Message):
    if not is_admin(message.from_user.id): return
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            ReplaceRequest.__table__.select().where(ReplaceRequest.status == 'pending')
        )
        reqs = result.fetchall()
        if not reqs:
            await message.answer("Нет активных заявок.")
            return
        for req in reqs:
            await message.answer(
                f"Заявка #{req.id}\nПользователь: {req.user_id}\nТелефон: {req.phone_number}\nДата: {req.date_time}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_replace_{req.id}"),
                     InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_replace_{req.id}")]
                ])
            )
