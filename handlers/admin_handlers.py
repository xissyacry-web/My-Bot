from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
from database.database import AsyncSessionLocal
from database.models import User, Product, Category, ReplaceRequest, Purchase, Promocode
from config import ADMIN_IDS
from utils.states import *
from services.product_service import get_categories, get_products_by_category
from sqlalchemy import select

router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@router.message(F.text == "/admin")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id): return
    from keyboards.inline import admin_main_keyboard
    await message.answer("🛠 Админ-панель:", reply_markup=admin_main_keyboard())

@router.callback_query(F.data == "admin_back")
async def back(callback: CallbackQuery):
    from keyboards.inline import admin_main_keyboard
    await callback.message.edit_text("🛠 Админ-панель:", reply_markup=admin_main_keyboard())
    await callback.answer()

# ---------- РАССЫЛКА ----------
@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите сообщение для рассылки всем пользователям:")
    await state.set_state(AdminBroadcast.message)

@router.message(AdminBroadcast.message)
async def broadcast_exec(message: Message, state: FSMContext):
    async with AsyncSessionLocal() as session:
        users = (await session.execute(select(User.user_id))).scalars().all()
    success = 0
    fail = 0
    for uid in users:
        try:
            await message.bot.send_message(uid, message.text)
            success += 1
        except:
            fail += 1
    await message.answer(f"📨 Рассылка завершена. Успешно: {success}, не доставлено: {fail}.")
    await state.clear()

# ---------- ДОБАВЛЕНИЕ ТОВАРА ----------
@router.callback_query(F.data == "admin_add_product")
async def add_prod(callback: CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session)
        if not cats:
            await callback.message.edit_text("Сначала создайте категорию через 'Добавить категорию'.")
            return
        text = "Категории:\n" + "\n".join(f"{c.id}: {c.name}" for c in cats)
        text += "\n\nВведите ID категории, куда добавить товар:"
    await callback.message.edit_text(text)
    await state.set_state(AdminAddProduct.category_id)

@router.message(AdminAddProduct.category_id)
async def ap_cat(message: Message, state: FSMContext):
    try:
        cat_id = int(message.text)
    except:
        await message.answer("Введите число")
        return
    async with AsyncSessionLocal() as session:
        cat = await session.get(Category, cat_id)
        if not cat:
            await message.answer("❌ Категория с таким ID не найдена. Попробуйте ещё раз.")
            return
    await state.update_data(category_id=cat_id)
    await message.answer("Введите название товара:")
    await state.set_state(AdminAddProduct.name)

@router.message(AdminAddProduct.name)
async def ap_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите цену за 1 шт. в $:")
    await state.set_state(AdminAddProduct.price)

@router.message(AdminAddProduct.price)
async def ap_price(message: Message, state: FSMContext):
    try:
        price = float(message.text)
    except:
        await message.answer("Введите число")
        return
    await state.update_data(price=price)
    await message.answer("Теперь отправьте текст товара. Каждая непустая строка = одна единица товара:")
    await state.set_state(AdminAddProduct.content)

@router.message(AdminAddProduct.content)
async def ap_content(message: Message, state: FSMContext):
    content = message.text
    lines = [line.strip() for line in content.split('\n') if line.strip()]
    quantity = len(lines)
    if quantity == 0:
        await message.answer("❌ Текст товара не может быть пустым.")
        return

    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        prod = Product(
            category_id=data['category_id'],
            name=data['name'],
            quantity=quantity,
            price=data['price'],
            content=content,
            file_id=None
        )
        session.add(prod)
        await session.commit()
    await message.answer(f"✅ Товар '{data['name']}' добавлен! Количество: {quantity} шт., Цена: {data['price']}$")
    await state.clear()

# ---------- КАТЕГОРИИ ----------
@router.callback_query(F.data == "admin_add_category")
async def add_cat(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите название новой категории:")
    await state.set_state(AdminAddCategory.name)

@router.message(AdminAddCategory.name)
async def cat_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("ID родительской категории (0 — верхний уровень):")
    await state.set_state(AdminAddCategory.parent_id)

@router.message(AdminAddCategory.parent_id)
async def cat_parent(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        pid = int(message.text)
        if pid == 0: pid = None
    except:
        await message.answer("Введите число")
        return
    async with AsyncSessionLocal() as session:
        cat = Category(name=data['name'], parent_id=pid)
        session.add(cat)
        await session.commit()
    await message.answer("✅ Категория добавлена!")
    await state.clear()

# ---------- УДАЛЕНИЕ ТОВАРА / КАТЕГОРИИ ----------
@router.callback_query(F.data == "admin_delete_product")
async def del_prod_cat(callback: CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session)
        if not cats:
            await callback.message.edit_text("Нет категорий")
            return
        from keyboards.inline import categories_keyboard
        await callback.message.edit_text("Выберите категорию:", reply_markup=categories_keyboard(cats))
    await state.set_state(AdminDeleteProduct.category_id)

@router.callback_query(AdminDeleteProduct.category_id, F.data.startswith("cat_"))
async def del_prod_list(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[1])
    await state.update_data(category_id=cat_id)
    async with AsyncSessionLocal() as session:
        prods = await get_products_by_category(session, cat_id)
        if not prods:
            await callback.answer("Нет товаров в этой категории", show_alert=True)
            return
        builder = InlineKeyboardBuilder()
        for p in prods:
            builder.button(text=f"{p.name} - {p.price}$", callback_data=f"delprod_{p.id}")
        builder.adjust(1)
        builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
        await callback.message.edit_text("Выберите товар для удаления:", reply_markup=builder.as_markup())
    await state.set_state(AdminDeleteProduct.product_id)

@router.callback_query(AdminDeleteProduct.product_id, F.data.startswith("delprod_"))
async def del_prod_exec(callback: CallbackQuery, state: FSMContext):
    pid = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        prod = await session.get(Product, pid)
        if prod:
            await session.delete(prod)
            await session.commit()
            await callback.message.edit_text("✅ Товар удалён")
        else:
            await callback.answer("Товар не найден")
    await state.clear()

@router.callback_query(F.data == "admin_delete_category")
async def del_cat(callback: CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session)
        if not cats:
            await callback.message.edit_text("Нет категорий")
            return
        from keyboards.inline import categories_keyboard
        await callback.message.edit_text("Выберите категорию для удаления:", reply_markup=categories_keyboard(cats))
    await state.set_state(AdminDeleteCategory.category_id)

@router.callback_query(AdminDeleteCategory.category_id, F.data.startswith("cat_"))
async def del_cat_exec(callback: CallbackQuery, state: FSMContext):
    cid = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        cat = await session.get(Category, cid)
        if cat:
            await session.delete(cat)
            await session.commit()
            await callback.message.edit_text("✅ Категория удалена")
        else:
            await callback.answer("Категория не найдена")
    await state.clear()

# ---------- ПРОМОКОДЫ ----------
@router.callback_query(F.data == "admin_promocodes")
async def promo_menu(callback: CallbackQuery):
    from keyboards.inline import admin_promocodes_keyboard
    await callback.message.edit_text("Промокоды:", reply_markup=admin_promocodes_keyboard())
    await callback.answer()

@router.callback_query(F.data == "promo_add")
async def promo_add_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите промокод (текст):")
    await state.set_state(AdminPromoAdd.code)

@router.message(AdminPromoAdd.code)
async def promo_code(message: Message, state: FSMContext):
    await state.update_data(code=message.text.strip())
    await message.answer("Сумма бонуса в $:")
    await state.set_state(AdminPromoAdd.amount)

@router.message(AdminPromoAdd.amount)
async def promo_amount(message: Message, state: FSMContext):
    try: amount = float(message.text)
    except: await message.answer("Введите число"); return
    await state.update_data(amount=amount)
    await message.answer("Макс. кол-во активаций (0 — безлимит):")
    await state.set_state(AdminPromoAdd.max_activations)

@router.message(AdminPromoAdd.max_activations)
async def promo_max(message: Message, state: FSMContext):
    try:
        max_a = int(message.text)
        if max_a == 0: max_a = None
    except: await message.answer("Введите число"); return
    await state.update_data(max_activations=max_a)
    await message.answer("Срок действия в днях (0 — бессрочно):")
    await state.set_state(AdminPromoAdd.expires_days)

@router.message(AdminPromoAdd.expires_days)
async def promo_exp(message: Message, state: FSMContext):
    try: days = int(message.text)
    except: await message.answer("Введите число"); return
    exp = datetime.utcnow() + timedelta(days=days) if days > 0 else None
    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        promo = Promocode(code=data['code'], bonus_amount=data['amount'],
                          max_activations=data['max_activations'], expires_at=exp)
        session.add(promo)
        await session.commit()
    await message.answer(f"✅ Промокод {data['code']} создан!")
    await state.clear()

@router.callback_query(F.data == "promo_delete")
async def promo_del_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите код промокода для удаления:")
    await state.set_state(AdminPromoDelete.code)

@router.message(AdminPromoDelete.code)
async def promo_del(message: Message, state: FSMContext):
    code = message.text.strip()
    async with AsyncSessionLocal() as session:
        promo = await session.get(Promocode, code)
        if promo:
            await session.delete(promo)
            await session.commit()
            await message.answer("✅ Промокод удалён")
        else:
            await message.answer("❌ Промокод не найден")
    await state.clear()

@router.callback_query(F.data == "promo_list")
async def promo_list(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        promos = (await session.execute(select(Promocode))).scalars().all()
        if not promos:
            await callback.answer("Нет промокодов", show_alert=True)
            return
        text = "Список промокодов:\n"
        for p in promos:
            exp = p.expires_at.strftime("%d.%m.%Y") if p.expires_at else "бессрочно"
            lim = f"{p.used_count}/{p.max_activations}" if p.max_activations else "безлимит"
            text += f"📌 {p.code}: {p.bonus_amount}$ (актив: {lim}, до {exp})\n"
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_promocodes")]]))
    await callback.answer()

# ---------- ПОЛЬЗОВАТЕЛИ ----------
@router.callback_query(F.data == "admin_users_menu")
async def users_menu(callback: CallbackQuery):
    from keyboards.inline import admin_users_keyboard
    await callback.message.edit_text("Пользователи:", reply_markup=admin_users_keyboard())
    await callback.answer()

@router.callback_query(F.data == "user_search")
async def user_search_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите Telegram ID:")
    await state.set_state(AdminUserSearch.user_id)

@router.message(AdminUserSearch.user_id)
async def user_search_res(message: Message, state: FSMContext):
    try: uid = int(message.text)
    except: await message.answer("Введите число"); return
    async with AsyncSessionLocal() as session:
        user = await session.get(User, uid)
        if user:
            await message.answer(f"ID: {user.user_id}\nUsername: @{user.username}\nБаланс: {user.balance:.2f}$\nБан: {'да' if user.is_banned else 'нет'}")
        else:
            await message.answer("Пользователь не найден.")
    await state.clear()

@router.callback_query(F.data == "user_balance")
async def user_bal_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите Telegram ID:")
    await state.set_state(AdminUserBalance.user_id)

@router.message(AdminUserBalance.user_id)
async def user_bal_uid(message: Message, state: FSMContext):
    try: uid = int(message.text)
    except: await message.answer("Введите число"); return
    await state.update_data(user_id=uid)
    await message.answer("Сумма (+/-):")
    await state.set_state(AdminUserBalance.amount)

@router.message(AdminUserBalance.amount)
async def user_bal_amount(message: Message, state: FSMContext):
    try: amount = float(message.text)
    except: await message.answer("Введите число"); return
    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        user = await session.get(User, data['user_id'])
        if user:
            user.balance += amount
            await session.commit()
            await message.answer(f"Баланс изменён. Текущий: {user.balance:.2f}$")
        else:
            await message.answer("Пользователь не найден.")
    await state.clear()

@router.callback_query(F.data == "user_ban")
async def user_ban_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите Telegram ID:")
    await state.set_state(AdminUserBan.user_id)

@router.message(AdminUserBan.user_id)
async def user_ban_exec(message: Message, state: FSMContext):
    try: uid = int(message.text)
    except: await message.answer("Введите число"); return
    async with AsyncSessionLocal() as session:
        user = await session.get(User, uid)
        if user:
            user.is_banned = not user.is_banned
            st = "забанен" if user.is_banned else "разбанен"
            await session.commit()
            await message.answer(f"Пользователь {uid} {st}.")
        else:
            await message.answer("Пользователь не найден.")
    await state.clear()

# ---------- ЗАМЕНЫ ----------
@router.callback_query(F.data == "admin_replaces")
async def admin_replaces(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        reqs = (await session.execute(select(ReplaceRequest).where(ReplaceRequest.status == 'pending'))).scalars().all()
        if not reqs:
            await callback.message.edit_text("Нет активных заявок.")
            return
        for req in reqs:
            await callback.message.answer(
                f"Заявка #{req.id}\nПользователь: {req.user_id}\nТелефон: {req.phone_number}\nДата: {req.date_time}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_replace_{req.id}"),
                     InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_replace_{req.id}")]
                ]))
    await callback.answer()

@router.callback_query(F.data.startswith("approve_replace_"))
async def app_replace(callback: CallbackQuery):
    rid = int(callback.data.split("_")[2])
    async with AsyncSessionLocal() as session:
        req = await session.get(ReplaceRequest, rid)
        if not req or req.status != 'pending':
            await callback.answer("Уже обработана"); return
        req.status = 'approved'
        purchase = await session.get(Purchase, req.purchase_id)
        product = await session.get(Product, purchase.product_id) if purchase else None
        await session.commit()
        try:
            await callback.bot.send_message(req.user_id, f"✅ Заявка #{rid} одобрена.")
            if product:
                if product.content:
                    await callback.bot.send_message(req.user_id, product.content)
                if product.file_id:
                    await callback.bot.send_document(req.user_id, product.file_id)
        except Exception as e:
            await callback.answer(f"Ошибка: {e}")
    await callback.message.edit_reply_markup()
    await callback.answer("Одобрено")

@router.callback_query(F.data.startswith("reject_replace_"))
async def rej_replace(callback: CallbackQuery, state: FSMContext):
    rid = int(callback.data.split("_")[2])
    await callback.message.answer("Введите причину отказа:")
    await state.set_state(AdminUserBan.user_id)
    await state.update_data(req_id=rid)
    await callback.answer()

@router.message(AdminUserBan.user_id)
async def rej_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    rid = data.get('req_id')
    if not rid:
        await message.answer("Ошибка состояния.")
        await state.clear()
        return
    async with AsyncSessionLocal() as session:
        req = await session.get(ReplaceRequest, rid)
        if req and req.status == 'pending':
            req.status = 'rejected'
            req.admin_comment = message.text
            await session.commit()
            try:
                await message.bot.send_message(req.user_id, f"❌ Заявка #{rid} отклонена. Причина: {message.text}")
                await message.answer("Отказ отправлен.")
            except:
                await message.answer("Не удалось уведомить.")
        else:
            await message.answer("Заявка уже обработана.")
    await state.clear()
