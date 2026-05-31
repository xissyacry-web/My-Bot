from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
from database.database import AsyncSessionLocal
from database.models import User, Product, Category, Promocode, UnbanRequest, Invoice, Purchase, ReplaceRequest
from config import ADMIN_IDS
from utils.states import *
from services.product_service import get_categories, get_products_by_category
from sqlalchemy import select, func

router = Router()
VERSION = "v1.0.8"

def is_admin(user_id: int) -> bool: return user_id in ADMIN_IDS

@router.message(F.text == "/admin")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id): return
    from keyboards.inline import admin_main_keyboard
    await message.answer(f"🛠 Админ-панель {VERSION}", reply_markup=admin_main_keyboard())

@router.callback_query(F.data == "admin_back")
async def back(callback: CallbackQuery):
    from keyboards.inline import admin_main_keyboard
    await callback.message.edit_text(f"🛠 Админ-панель {VERSION}", reply_markup=admin_main_keyboard())
    await callback.answer()

# --- Статистика ---
@router.callback_query(F.data == "admin_stats")
async def stats_menu(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="День", callback_data="stats_day")
    builder.button(text="7 дней", callback_data="stats_week")
    builder.button(text="30 дней", callback_data="stats_month")
    builder.button(text="🔙 Назад", callback_data="admin_back")
    await callback.message.edit_text("Период:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("stats_"))
async def stats_show(callback: CallbackQuery):
    days = int(callback.data.split("_")[1]) if callback.data.split("_")[1].isdigit() else 1
    since = datetime.utcnow() - timedelta(days=days)
    async with AsyncSessionLocal() as session:
        new_users = (await session.execute(select(func.count(User.user_id)).where(User.registered_at >= since))).scalar()
        purchases = (await session.execute(select(func.count(Purchase.id)).where(Purchase.purchased_at >= since))).scalar()
        refills = (await session.execute(select(func.count(Invoice.id)).where(Invoice.created_at >= since, Invoice.status == 'paid'))).scalar()
        refills_sum = (await session.execute(select(func.sum(Invoice.amount)).where(Invoice.created_at >= since, Invoice.status == 'paid'))).scalar() or 0.0
    text = (f"📊 Статистика за {days} дн.\n"
            f"👥 Новых: {new_users}\n🛒 Покупок: {purchases}\n"
            f"💰 Пополнений: {refills} на {refills_sum:.2f}$")
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_stats")]]))

# --- Рассылка ---
@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите сообщение:")
    await state.set_state(AdminBroadcast.message)

@router.message(AdminBroadcast.message)
async def broadcast_exec(message: Message, state: FSMContext):
    async with AsyncSessionLocal() as session:
        users = (await session.execute(select(User.user_id))).scalars().all()
    s = f = 0
    for uid in users:
        try: await message.bot.send_message(uid, message.text); s += 1
        except: f += 1
    from services.log_service import log_broadcast
    await log_broadcast(message.bot, message.from_user.id, message.text, s, f)
    await message.answer(f"📨 Успешно: {s}, не доставлено: {f}.")
    await state.clear()

# --- Товары и категории (добавление, удаление) ---
@router.callback_query(F.data == "admin_add_product")
async def add_prod(callback: CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session)
        if not cats: await callback.message.edit_text("Нет категорий."); return
        text = "Категории:\n" + "\n".join(f"{c.id}: {c.name}" for c in cats) + "\n\nВведите ID категории:"
    await callback.message.edit_text(text)
    await state.set_state(AdminAddProduct.category_id)

@router.message(AdminAddProduct.category_id)
async def ap_cat(message: Message, state: FSMContext):
    try: cat_id = int(message.text)
    except: await message.answer("Число!"); return
    async with AsyncSessionLocal() as session:
        if not await session.get(Category, cat_id): await message.answer("❌ Не найдена."); return
    await state.update_data(category_id=cat_id)
    await message.answer("Название товара:"); await state.set_state(AdminAddProduct.name)

@router.message(AdminAddProduct.name)
async def ap_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Описание:"); await state.set_state(AdminAddProduct.description)

@router.message(AdminAddProduct.description)
async def ap_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Цена за 1 шт. в $:"); await state.set_state(AdminAddProduct.price)

@router.message(AdminAddProduct.price)
async def ap_price(message: Message, state: FSMContext):
    try: price = float(message.text)
    except: await message.answer("Число!"); return
    await state.update_data(price=price)
    await message.answer("Количество (0 – бесконечно):"); await state.set_state(AdminAddProduct.quantity)

@router.message(AdminAddProduct.quantity)
async def ap_qty(message: Message, state: FSMContext):
    try: qty = int(message.text); assert qty >= 0
    except: await message.answer("Целое ≥0"); return
    await state.update_data(quantity=qty)
    await message.answer("Текст товара (строки = единицы) или '-' если файл:"); await state.set_state(AdminAddProduct.content)

@router.message(AdminAddProduct.content)
async def ap_content(message: Message, state: FSMContext):
    data = await state.get_data(); quantity = data['quantity']
    if message.text.strip() == '-': content = None; lines = 0
    else:
        content = message.text; lines = [l.strip() for l in content.split('\n') if l.strip()]
        if not lines: await message.answer("Пусто. Повторите или '-'."); return
    if quantity > 0 and len(lines) != quantity:
        await message.answer(f"❌ Указано {quantity}, строк {len(lines)}. Повторите."); return
    await state.update_data(content=content)
    await message.answer("Файл (или '-'):"); await state.set_state(AdminAddProduct.file)

@router.message(AdminAddProduct.file)
async def ap_file(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.document: file_id = message.document.file_id
    elif message.photo: file_id = message.photo[-1].file_id
    else: file_id = None
    if not data.get('content') and not file_id:
        await message.answer("❌ Нужен текст или файл."); return
    async with AsyncSessionLocal() as session:
        prod = Product(category_id=data['category_id'], name=data['name'], description=data['description'],
                       price=data['price'], quantity=data['quantity'], content=data.get('content'), file_id=file_id)
        session.add(prod); await session.commit()
    await message.answer(f"✅ Товар '{data['name']}' добавлен!")
    await state.clear()

@router.callback_query(F.data == "admin_add_category")
async def add_cat(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Название:"); await state.set_state(AdminAddCategory.name)

@router.message(AdminAddCategory.name)
async def cat_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("ID родителя (0 – верхний):"); await state.set_state(AdminAddCategory.parent_id)

@router.message(AdminAddCategory.parent_id)
async def cat_parent(message: Message, state: FSMContext):
    try: pid = int(message.text)
    except: await message.answer("Число!"); return
    if pid == 0: pid = None
    else:
        async with AsyncSessionLocal() as session:
            if not await session.get(Category, pid): await message.answer("❌ Не найден."); return
    async with AsyncSessionLocal() as session:
        session.add(Category(name=(await state.get_data())['name'], parent_id=pid))
        await session.commit()
    await message.answer("✅ Категория добавлена!"); await state.clear()

@router.callback_query(F.data == "admin_delete_product")
async def del_prod_cat(callback: CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session)
        if not cats: await callback.message.edit_text("Нет категорий"); return
        builder = InlineKeyboardBuilder()
        for c in cats: builder.button(text=c.name, callback_data=f"delcat_{c.id}")
        builder.adjust(2); builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
        await callback.message.edit_text("Выберите категорию:", reply_markup=builder.as_markup())
    await state.set_state(AdminDeleteProduct.category_id)

@router.callback_query(AdminDeleteProduct.category_id, F.data.startswith("delcat_"))
async def del_prod_list(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[1]); await state.update_data(category_id=cat_id)
    async with AsyncSessionLocal() as session:
        prods = await get_products_by_category(session, cat_id)
        if not prods: await callback.answer("Нет товаров", show_alert=True); return
        builder = InlineKeyboardBuilder()
        for p in prods: builder.button(text=f"{p.name} - {p.price}$", callback_data=f"delprod_{p.id}")
        builder.adjust(1); builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
        await callback.message.edit_text("Выберите товар:", reply_markup=builder.as_markup())
    await state.set_state(AdminDeleteProduct.product_id)

@router.callback_query(AdminDeleteProduct.product_id, F.data.startswith("delprod_"))
async def del_prod_exec(callback: CallbackQuery, state: FSMContext):
    pid = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        prod = await session.get(Product, pid)
        if prod: await session.delete(prod); await session.commit(); await callback.message.edit_text("✅ Товар удалён")
        else: await callback.answer("Не найден")
    await state.clear()

@router.callback_query(F.data == "admin_delete_category")
async def del_cat(callback: CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session)
        if not cats: await callback.message.edit_text("Нет категорий"); return
        builder = InlineKeyboardBuilder()
        for c in cats: builder.button(text=c.name, callback_data=f"delcat_{c.id}")
        builder.adjust(2); builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
        await callback.message.edit_text("Выберите категорию:", reply_markup=builder.as_markup())
    await state.set_state(AdminDeleteCategory.category_id)

@router.callback_query(AdminDeleteCategory.category_id, F.data.startswith("delcat_"))
async def del_cat_exec(callback: CallbackQuery, state: FSMContext):
    cid = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        cat = await session.get(Category, cid)
        if not cat: await callback.answer("Не найдена"); await state.clear(); return
        subcats = (await session.execute(select(Category).where(Category.parent_id == cid))).scalars().all()
        products = (await session.execute(select(Product).where(Product.category_id == cid))).scalars().all()
        if subcats or products:
            await callback.message.edit_text("❌ Сначала удалите товары/подкатегории."); await state.clear(); return
        await session.delete(cat); await session.commit(); await callback.message.edit_text("✅ Категория удалена")
    await state.clear()

# --- Промокоды ---
@router.callback_query(F.data == "admin_promocodes")
async def promo_menu(callback: CallbackQuery):
    from keyboards.inline import admin_promocodes_keyboard
    await callback.message.edit_text("Промокоды:", reply_markup=admin_promocodes_keyboard()); await callback.answer()

@router.callback_query(F.data == "promo_add")
async def promo_add_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Код:"); await state.set_state(AdminPromoAdd.code)

@router.message(AdminPromoAdd.code)
async def promo_code(message: Message, state: FSMContext):
    await state.update_data(code=message.text.strip())
    await message.answer("Сумма бонуса $:"); await state.set_state(AdminPromoAdd.amount)

@router.message(AdminPromoAdd.amount)
async def promo_amount(message: Message, state: FSMContext):
    try: amt = float(message.text)
    except: await message.answer("Число"); return
    await state.update_data(amount=amt)
    await message.answer("Макс. активаций (0 безлимит):"); await state.set_state(AdminPromoAdd.max_activations)

@router.message(AdminPromoAdd.max_activations)
async def promo_max(message: Message, state: FSMContext):
    try: mx = int(message.text); mx = None if mx == 0 else mx
    except: await message.answer("Число"); return
    await state.update_data(max_activations=mx)
    await message.answer("Дней действия (0 бессрочно):"); await state.set_state(AdminPromoAdd.expires_days)

@router.message(AdminPromoAdd.expires_days)
async def promo_exp(message: Message, state: FSMContext):
    try: days = int(message.text)
    except: await message.answer("Число"); return
    exp = datetime.utcnow() + timedelta(days=days) if days > 0 else None
    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        promo = Promocode(code=data['code'], bonus_amount=data['amount'], max_activations=data['max_activations'], expires_at=exp)
        session.add(promo); await session.commit()
    await message.answer(f"✅ Промокод {data['code']} создан!"); await state.clear()

@router.callback_query(F.data == "promo_delete")
async def promo_del_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Код для удаления:"); await state.set_state(AdminPromoDelete.code)

@router.message(AdminPromoDelete.code)
async def promo_del(message: Message, state: FSMContext):
    code = message.text.strip()
    async with AsyncSessionLocal() as session:
        promo = await session.get(Promocode, code)
        if promo: await session.delete(promo); await session.commit(); await message.answer("✅ Удалён")
        else: await message.answer("❌ Не найден")
    await state.clear()

@router.callback_query(F.data == "promo_list")
async def promo_list(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        promos = (await session.execute(select(Promocode))).scalars().all()
        if not promos: await callback.answer("Нет", show_alert=True); return
        text = "Список:\n"
        for p in promos:
            exp = p.expires_at.strftime("%d.%m.%Y") if p.expires_at else "бессрочно"
            lim = f"{p.used_count}/{p.max_activations}" if p.max_activations else "безлимит"
            text += f"📌 {p.code}: {p.bonus_amount}$ (актив: {lim}, до {exp})\n"
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_promocodes")]]))

# --- Пользователи ---
@router.callback_query(F.data == "admin_users_menu")
async def users_menu(callback: CallbackQuery):
    from keyboards.inline import admin_users_keyboard
    await callback.message.edit_text("Пользователи:", reply_markup=admin_users_keyboard()); await callback.answer()

@router.callback_query(F.data == "user_search")
async def user_search_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Telegram ID:"); await state.set_state(AdminUserSearch.user_id)

@router.message(AdminUserSearch.user_id)
async def user_search_res(message: Message, state: FSMContext):
    try: uid = int(message.text)
    except: await message.answer("Число"); return
    async with AsyncSessionLocal() as session:
        user = await session.get(User, uid)
        if user: await message.answer(f"ID: {user.user_id}\n@{user.username}\nБаланс: {user.balance:.2f}$\nБан: {'да' if user.is_banned else 'нет'} ({user.ban_reason or '-'})")
        else: await message.answer("Не найден.")
    await state.clear()

@router.callback_query(F.data == "user_balance")
async def user_bal_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Telegram ID:"); await state.set_state(AdminUserBalance.user_id)

@router.message(AdminUserBalance.user_id)
async def user_bal_uid(message: Message, state: FSMContext):
    try: uid = int(message.text)
    except: await message.answer("Число"); return
    await state.update_data(user_id=uid)
    await message.answer("Сумма (+/-):"); await state.set_state(AdminUserBalance.amount)

@router.message(AdminUserBalance.amount)
async def user_bal_amount(message: Message, state: FSMContext):
    try: amount = float(message.text)
    except: await message.answer("Число"); return
    data = await state.get_data(); uid = data['user_id']
    async with AsyncSessionLocal() as session:
        user = await session.get(User, uid)
        if user:
            user.balance += amount; await session.commit()
            act = "пополнен" if amount >= 0 else "списан"
            try: await message.bot.send_message(uid, f"💰 Баланс {act} на {abs(amount):.2f}$\nТекущий: {user.balance:.2f}$")
            except: pass
            await message.answer(f"Баланс {uid} изменён. Текущий: {user.balance:.2f}$")
        else: await message.answer("Не найден.")
    await state.clear()

@router.callback_query(F.data == "user_ban")
async def user_ban_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Telegram ID:"); await state.set_state(AdminUserBan.user_id)

@router.message(AdminUserBan.user_id)
async def user_ban_uid(message: Message, state: FSMContext):
    try: uid = int(message.text)
    except: await message.answer("Число"); return
    await state.update_data(user_id=uid)
    await message.answer("Причина бана (или '-' для разбана):"); await state.set_state(AdminUserBan.reason)

@router.message(AdminUserBan.reason)
async def user_ban_exec(message: Message, state: FSMContext):
    reason = message.text; data = await state.get_data(); uid = data['user_id']
    async with AsyncSessionLocal() as session:
        user = await session.get(User, uid)
        if user:
            if reason.strip() == '-':
                user.is_banned = False; user.ban_reason = None; st = "разбанен"
                try: await message.bot.send_message(uid, "✅ Вы разблокированы.")
                except: pass
            else:
                user.is_banned = True; user.ban_reason = reason; st = "забанен"
                try: await message.bot.send_message(uid, f"🚫 Заблокированы.\nПричина: {reason}")
                except: pass
            await session.commit(); await message.answer(f"Пользователь {uid} {st}.")
        else: await message.answer("Не найден.")
    await state.clear()

# --- Разжалования ---
@router.callback_query(F.data.startswith("unban_approve_"))
async def unban_approve(callback: CallbackQuery):
    rid = int(callback.data.split("_")[2])
    async with AsyncSessionLocal() as session:
        req = await session.get(UnbanRequest, rid)
        if not req or req.status != 'pending': await callback.answer("Обработана"); return
        req.status = 'approved'; user = await session.get(User, req.user_id)
        if user: user.is_banned = False; user.ban_reason = None
        await session.commit()
        await callback.bot.send_message(req.user_id, "✅ Разжалование одобрено!")
        await callback.message.edit_text(f"✅ Пользователь {req.user_id} разблокирован.")
    await callback.answer()

@router.callback_query(F.data.startswith("unban_reject_"))
async def unban_reject(callback: CallbackQuery):
    rid = int(callback.data.split("_")[2])
    async with AsyncSessionLocal() as session:
        req = await session.get(UnbanRequest, rid)
        if not req or req.status != 'pending': await callback.answer("Обработана"); return
        req.status = 'rejected'; await session.commit()
        await callback.bot.send_message(req.user_id, "❌ Разжалование отклонено.")
        await callback.message.edit_text(f"❌ Заявка #{rid} отклонена.")
    await callback.answer()

# ========== ЗАМЕНА (АДМИН) ==========
@router.callback_query(F.data == "admin_replaces")
async def admin_replaces(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        reqs = (await session.execute(select(ReplaceRequest).where(ReplaceRequest.status == 'pending'))).scalars().all()
        if not reqs: await callback.message.edit_text("Нет активных заявок."); return
        for req in reqs:
            text = f"Заявка #{req.id}\n👤 {req.user_id}\nЛог/время: {req.log_info}\nЖалоба: {req.complaint or '-'}"
            if req.photos:
                photo_ids = req.photos.split(',')
                if photo_ids:
                    media = [InputMediaPhoto(media=pid) for pid in photo_ids]
                    await callback.message.answer_media_group(media)
            await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"replace_approve_{req.id}"),
                 InlineKeyboardButton(text="❌ Отказать", callback_data=f"replace_reject_{req.id}")]]))
    await callback.answer()

@router.callback_query(F.data.startswith("replace_approve_"))
async def replace_approve(callback: CallbackQuery, state: FSMContext):
    rid = int(callback.data.split("_")[2])
    await callback.message.answer("Введите сообщение для пользователя (можно прикрепить файл):")
    await state.set_state(AdminReplaceApprove.message)
    await state.update_data(req_id=rid)
    await callback.answer()

@router.message(AdminReplaceApprove.message)
async def replace_approve_msg(message: Message, state: FSMContext):
    data = await state.get_data(); rid = data['req_id']
    # Получаем файл, если есть
    file_id = None
    if message.document: file_id = message.document.file_id
    elif message.photo: file_id = message.photo[-1].file_id
    # Отправляем пользователю
    async with AsyncSessionLocal() as session:
        req = await session.get(ReplaceRequest, rid)
        if not req or req.status != 'pending': await message.answer("Заявка уже обработана."); await state.clear(); return
        req.status = 'approved'; req.admin_comment = message.text or ""
        await session.commit()
        try:
            await message.bot.send_message(req.user_id, f"✅ Замена #{rid} одобрена.\nАдминистратор: {message.text or 'без текста'}")
            if file_id:
                try: await message.bot.send_document(req.user_id, file_id) if file_id else None
                except: pass
        except: pass
    await message.answer("Одобрено."); await state.clear()

@router.callback_query(F.data.startswith("replace_reject_"))
async def replace_reject(callback: CallbackQuery, state: FSMContext):
    rid = int(callback.data.split("_")[2])
    await callback.message.answer("Введите причину отказа:")
    await state.set_state(AdminReplaceReject.reason)
    await state.update_data(req_id=rid)
    await callback.answer()

@router.message(AdminReplaceReject.reason)
async def replace_reject_reason(message: Message, state: FSMContext):
    data = await state.get_data(); rid = data['req_id']
    reason = message.text
    async with AsyncSessionLocal() as session:
        req = await session.get(ReplaceRequest, rid)
        if not req or req.status != 'pending': await message.answer("Уже обработана."); await state.clear(); return
        req.status = 'rejected'; req.admin_comment = reason; await session.commit()
        try: await message.bot.send_message(req.user_id, f"❌ Замена #{rid} отклонена.\nПричина: {reason}")
        except: pass
    await message.answer("Отказ отправлен."); await state.clear()
