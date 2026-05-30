from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
from database.database import AsyncSessionLocal
from database.models import User, Product, Category, ReplaceRequest, Purchase, Promocode, UnbanRequest, Invoice
from config import ADMIN_IDS, BOT_ACTIVE, TECH_MODE
from utils.states import *
from services.product_service import get_categories, get_products_by_category
from sqlalchemy import select, func, text
import os, sys, sqlite3, shutil

router = Router()

VERSION = "v1.0.6"

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# ---------- ГЛАВНОЕ МЕНЮ АДМИНА ----------
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

# ---------- ВКЛЮЧЕНИЕ / ВЫКЛЮЧЕНИЕ БОТА ----------
@router.callback_query(F.data == "admin_toggle_bot")
async def toggle_bot(callback: CallbackQuery):
    import config
    config.BOT_ACTIVE = not config.BOT_ACTIVE
    state = "выключен 🔴" if not config.BOT_ACTIVE else "включен 🟢"
    from keyboards.inline import admin_main_keyboard
    await callback.message.edit_text(f"🛠 Админ-панель {VERSION}\n\nБот {state}.", reply_markup=admin_main_keyboard())
    await callback.answer()

# ---------- ТЕХ. РЕЖИМ ----------
@router.callback_query(F.data == "admin_toggle_tech")
async def toggle_tech(callback: CallbackQuery):
    import config
    config.TECH_MODE = not config.TECH_MODE
    state = "включены 🔧" if config.TECH_MODE else "выключены"
    from keyboards.inline import admin_main_keyboard
    await callback.message.edit_text(f"🛠 Админ-панель {VERSION}\n\nТех. работы {state}.", reply_markup=admin_main_keyboard())
    await callback.answer()

# ---------- СТАТИСТИКА ----------
@router.callback_query(F.data == "admin_stats")
async def stats_menu(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="День", callback_data="stats_day")
    builder.button(text="7 дней", callback_data="stats_week")
    builder.button(text="30 дней", callback_data="stats_month")
    builder.button(text="🔙 Назад", callback_data="admin_back")
    await callback.message.edit_text("Выберите период:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("stats_"))
async def stats_show(callback: CallbackQuery):
    period = callback.data.split("_")[1]
    days = 1 if period == "day" else 7 if period == "week" else 30
    since = datetime.utcnow() - timedelta(days=days)
    async with AsyncSessionLocal() as session:
        new_users = (await session.execute(select(func.count(User.user_id)).where(User.registered_at >= since))).scalar()
        purchases = (await session.execute(select(func.count(Purchase.id)).where(Purchase.purchased_at >= since))).scalar()
        refills = (await session.execute(select(func.count(Invoice.id)).where(Invoice.created_at >= since, Invoice.status == 'paid'))).scalar()
        refills_sum = (await session.execute(select(func.sum(Invoice.amount)).where(Invoice.created_at >= since, Invoice.status == 'paid'))).scalar() or 0.0
    text = (f"📊 Статистика за {days} дн.\n"
            f"Новых пользователей: {new_users}\n"
            f"Покупок: {purchases}\n"
            f"Пополнений: {refills} на сумму {refills_sum:.2f}$")
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_stats")]]))

# ---------- ЭКСПОРТ / ИМПОРТ (БЕЗОПАСНЫЙ) ----------
@router.callback_query(F.data == "admin_export")
async def export_db(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        await session.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
        await session.commit()
    try:
        conn = sqlite3.connect("bot.db")
        cur = conn.execute("SELECT COUNT(*) FROM users")
        user_count = cur.fetchone()[0]
        cur = conn.execute("SELECT COUNT(*) FROM promocodes")
        promo_count = cur.fetchone()[0]
        conn.close()
        stat_text = f"👥 Пользователей: {user_count}\n🎁 Промокодов: {promo_count}"
    except Exception as e:
        stat_text = f"Ошибка проверки: {e}"
    try:
        await callback.message.answer_document(
            FSInputFile("bot.db"),
            caption=f"📤 Экспорт базы данных\n{stat_text}"
        )
    except Exception as e:
        await callback.message.answer(f"Ошибка экспорта: {e}")

@router.callback_query(F.data == "admin_import")
async def import_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "⚠️ Рекомендуется включить тех. работы перед импортом.\n"
        "Отправьте файл bot.db или нажмите «Отмена».",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data="admin_back")]
        ])
    )
    await state.set_state(AdminImport.file)

@router.message(AdminImport.file, F.document)
async def import_file(message: Message, state: FSMContext):
    if not message.document.file_name.endswith(".db"):
        await message.answer("❌ Принимается только файл с расширением .db")
        return
    file_id = message.document.file_id
    file = await message.bot.get_file(file_id)
    temp_path = "bot.db.uploaded"
    await message.bot.download_file(file.file_path, temp_path)
    try:
        conn = sqlite3.connect(temp_path)
        conn.execute("SELECT 1 FROM users LIMIT 1")
        conn.execute("SELECT 1 FROM promocodes LIMIT 1")
        conn.close()
    except Exception:
        await message.answer("❌ Файл не является базой данных бота или повреждён.")
        os.remove(temp_path)
        return
    if os.path.exists("bot.db"):
        shutil.copy2("bot.db", "backup.db")
        await message.answer("📦 Резервная копия сохранена как backup.db")
    os.replace(temp_path, "bot.db")
    await message.answer("✅ База данных импортирована. Бот будет перезапущен...")
    sys.exit(0)

# ---------- РАССЫЛКА ----------
@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите сообщение для рассылки:")
    await state.set_state(AdminBroadcast.message)

@router.message(AdminBroadcast.message)
async def broadcast_exec(message: Message, state: FSMContext):
    async with AsyncSessionLocal() as session:
        users = (await session.execute(select(User.user_id))).scalars().all()
    success = fail = 0
    for uid in users:
        try:
            await message.bot.send_message(uid, message.text)
            success += 1
        except:
            fail += 1
    from services.log_service import log_broadcast
    await log_broadcast(message.bot, message.from_user.id, message.text, success, fail)
    await message.answer(f"📨 Рассылка завершена. Успешно: {success}, не доставлено: {fail}.")
    await state.clear()

# ---------- ДОБАВЛЕНИЕ ТОВАРА ----------
@router.callback_query(F.data == "admin_add_product")
async def add_prod(callback: CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session)
        if not cats:
            await callback.message.edit_text("Сначала создайте категорию.")
            return
        text = "Категории:\n" + "\n".join(f"{c.id}: {c.name}" for c in cats)
        text += "\n\nВведите ID категории:"
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
        if not await session.get(Category, cat_id):
            await message.answer("❌ Категория не найдена.")
            return
    await state.update_data(category_id=cat_id)
    await message.answer("Введите название товара:")
    await state.set_state(AdminAddProduct.name)

@router.message(AdminAddProduct.name)
async def ap_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите описание товара (то, что увидят в меню):")
    await state.set_state(AdminAddProduct.description)

@router.message(AdminAddProduct.description)
async def ap_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
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
    await message.answer("Введите количество (0 – бесконечно):")
    await state.set_state(AdminAddProduct.quantity)

@router.message(AdminAddProduct.quantity)
async def ap_qty(message: Message, state: FSMContext):
    try:
        qty = int(message.text)
        if qty < 0:
            raise ValueError
    except:
        await message.answer("Введите целое число (0 или больше)")
        return
    await state.update_data(quantity=qty)
    await message.answer("Отправьте текст товара (каждая непустая строка = одна единица) или '-' если товар только файлом:")
    await state.set_state(AdminAddProduct.content)

@router.message(AdminAddProduct.content)
async def ap_content(message: Message, state: FSMContext):
    data = await state.get_data()
    quantity = data['quantity']
    if message.text.strip() == '-':
        content = None
        lines_count = 0
    else:
        content = message.text
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        lines_count = len(lines)
        if lines_count == 0:
            await message.answer("❌ Текст не может быть пустым. Отправьте хотя бы одну строку или '-'")
            return
    if quantity > 0 and lines_count != quantity:
        await message.answer(f"❌ Вы указали количество {quantity}, но в тексте {lines_count} строк. Отправьте текст снова.")
        return
    await state.update_data(content=content)
    await message.answer("Отправьте файл товара (документ/фото) или '-' если не нужен:")
    await state.set_state(AdminAddProduct.file)

@router.message(AdminAddProduct.file)
async def ap_file(message: Message, state: FSMContext):
    data = await state.get_data()
    quantity = data['quantity']
    content = data.get('content')
    if message.document:
        file_id = message.document.file_id
    elif message.photo:
        file_id = message.photo[-1].file_id
    else:
        file_id = None
    if not content and not file_id:
        await message.answer("❌ Нужен хотя бы текст или файл.")
        return
    async with AsyncSessionLocal() as session:
        prod = Product(
            category_id=data['category_id'],
            name=data['name'],
            description=data['description'],
            price=data['price'],
            quantity=quantity,
            content=content,
            file_id=file_id
        )
        session.add(prod)
        await session.commit()
    await message.answer(f"✅ Товар '{data['name']}' добавлен!")
    await state.clear()

# ---------- ДОБАВЛЕНИЕ КАТЕГОРИИ ----------
@router.callback_query(F.data == "admin_add_category")
async def add_cat(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите название новой категории:")
    await state.set_state(AdminAddCategory.name)

@router.message(AdminAddCategory.name)
async def cat_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите ID родительской категории (0 — если верхний уровень):")
    await state.set_state(AdminAddCategory.parent_id)

@router.message(AdminAddCategory.parent_id)
async def cat_parent(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        pid = int(message.text)
        if pid == 0:
            pid = None
        else:
            async with AsyncSessionLocal() as session:
                if not await session.get(Category, pid):
                    await message.answer("❌ Родительская категория не найдена. Введите ID ещё раз или 0:")
                    return
    except:
        await message.answer("Введите число")
        return
    async with AsyncSessionLocal() as session:
        cat = Category(name=data['name'], parent_id=pid)
        session.add(cat)
        await session.commit()
    await message.answer("✅ Категория добавлена!")
    await state.clear()

# ---------- УДАЛЕНИЕ ТОВАРА ----------
@router.callback_query(F.data == "admin_delete_product")
async def del_prod_cat(callback: CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session)
        if not cats:
            await callback.message.edit_text("Нет категорий")
            return
        builder = InlineKeyboardBuilder()
        for c in cats:
            builder.button(text=c.name, callback_data=f"delcat_{c.id}")
        builder.adjust(2)
        builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
        await callback.message.edit_text("Выберите категорию, в которой находится товар:", reply_markup=builder.as_markup())
    await state.set_state(AdminDeleteProduct.category_id)

@router.callback_query(AdminDeleteProduct.category_id, F.data.startswith("delcat_"))
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

# ---------- УДАЛЕНИЕ КАТЕГОРИИ (БЕЗОПАСНОЕ) ----------
@router.callback_query(F.data == "admin_delete_category")
async def del_cat(callback: CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session)
        if not cats:
            await callback.message.edit_text("Нет категорий")
            return
        builder = InlineKeyboardBuilder()
        for c in cats:
            builder.button(text=c.name, callback_data=f"delcat_{c.id}")
        builder.adjust(2)
        builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
        await callback.message.edit_text("Выберите категорию для удаления:", reply_markup=builder.as_markup())
    await state.set_state(AdminDeleteCategory.category_id)

@router.callback_query(AdminDeleteCategory.category_id, F.data.startswith("delcat_"))
async def del_cat_exec(callback: CallbackQuery, state: FSMContext):
    cid = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        cat = await session.get(Category, cid)
        if not cat:
            await callback.answer("Категория не найдена")
            await state.clear()
            return
        subcats = (await session.execute(select(Category).where(Category.parent_id == cid))).scalars().all()
        products = (await session.execute(select(Product).where(Product.category_id == cid))).scalars().all()
        if subcats or products:
            await callback.message.edit_text("❌ Нельзя удалить категорию, в которой есть товары или подкатегории. Сначала удалите их.")
            await state.clear()
            return
        await session.delete(cat)
        await session.commit()
        await callback.message.edit_text("✅ Категория удалена")
    await state.clear()

# ---------- ПРОМОКОДЫ ----------
@router.callback_query(F.data == "admin_promocodes")
async def promo_menu(callback: CallbackQuery):
    from keyboards.inline import admin_promocodes_keyboard
    await callback.message.edit_text("Промокоды:", reply_markup=admin_promocodes_keyboard())
    await callback.answer()

@router.callback_query(F.data == "promo_add")
async def promo_add_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите промокод:")
    await state.set_state(AdminPromoAdd.code)

@router.message(AdminPromoAdd.code)
async def promo_code(message: Message, state: FSMContext):
    await state.update_data(code=message.text.strip())
    await message.answer("Сумма бонуса в $:")
    await state.set_state(AdminPromoAdd.amount)

@router.message(AdminPromoAdd.amount)
async def promo_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text)
    except:
        await message.answer("Введите число")
        return
    await state.update_data(amount=amount)
    await message.answer("Макс. активаций (0 – безлимит):")
    await state.set_state(AdminPromoAdd.max_activations)

@router.message(AdminPromoAdd.max_activations)
async def promo_max(message: Message, state: FSMContext):
    try:
        max_a = int(message.text)
        if max_a == 0:
            max_a = None
    except:
        await message.answer("Введите число")
        return
    await state.update_data(max_activations=max_a)
    await message.answer("Срок действия в днях (0 – бессрочно):")
    await state.set_state(AdminPromoAdd.expires_days)

@router.message(AdminPromoAdd.expires_days)
async def promo_exp(message: Message, state: FSMContext):
    try:
        days = int(message.text)
    except:
        await message.answer("Введите число")
        return
    exp = datetime.utcnow() + timedelta(days=days) if days > 0 else None
    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        promo = Promocode(
            code=data['code'],
            bonus_amount=data['amount'],
            max_activations=data['max_activations'],
            expires_at=exp
        )
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
    try:
        uid = int(message.text)
    except:
        await message.answer("Введите число")
        return
    async with AsyncSessionLocal() as session:
        user = await session.get(User, uid)
        if user:
            await message.answer(f"ID: {user.user_id}\nUsername: @{user.username}\nБаланс: {user.balance:.2f}$\nБан: {'да' if user.is_banned else 'нет'}, причина: {user.ban_reason or '-'}")
        else:
            await message.answer("Пользователь не найден.")
    await state.clear()

@router.callback_query(F.data == "user_balance")
async def user_bal_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите Telegram ID:")
    await state.set_state(AdminUserBalance.user_id)

@router.message(AdminUserBalance.user_id)
async def user_bal_uid(message: Message, state: FSMContext):
    try:
        uid = int(message.text)
    except:
        await message.answer("Введите число")
        return
    await state.update_data(user_id=uid)
    await message.answer("Сумма (+ начислить, - списать):")
    await state.set_state(AdminUserBalance.amount)

@router.message(AdminUserBalance.amount)
async def user_bal_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text)
    except:
        await message.answer("Введите число")
        return
    data = await state.get_data()
    uid = data['user_id']
    async with AsyncSessionLocal() as session:
        user = await session.get(User, uid)
        if user:
            user.balance += amount
            await session.commit()
            action = "пополнен" if amount >= 0 else "списан"
            try:
                await message.bot.send_message(uid, f"💰 Ваш баланс {action} на {abs(amount):.2f}$ администратором.\nТекущий баланс: {user.balance:.2f}$")
            except:
                pass
            await message.answer(f"Баланс пользователя {uid} изменён. Текущий: {user.balance:.2f}$")
        else:
            await message.answer("Пользователь не найден.")
    await state.clear()

@router.callback_query(F.data == "user_ban")
async def user_ban_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите Telegram ID для бана/разбана:")
    await state.set_state(AdminUserBan.user_id)

@router.message(AdminUserBan.user_id)
async def user_ban_uid(message: Message, state: FSMContext):
    try:
        uid = int(message.text)
    except:
        await message.answer("Введите число")
        return
    await state.update_data(user_id=uid)
    await message.answer("Введите причину бана (или '-' если разбан):")
    await state.set_state(AdminUserBan.reason)

@router.message(AdminUserBan.reason)
async def user_ban_exec(message: Message, state: FSMContext):
    reason = message.text
    data = await state.get_data()
    uid = data['user_id']
    async with AsyncSessionLocal() as session:
        user = await session.get(User, uid)
        if user:
            if reason.strip() == '-':
                user.is_banned = False
                user.ban_reason = None
                st = "разбанен"
                try:
                    await message.bot.send_message(uid, "✅ Вы были разблокированы администратором.")
                except:
                    pass
            else:
                user.is_banned = True
                user.ban_reason = reason
                st = "забанен"
                try:
                    await message.bot.send_message(uid, f"🚫 Вы заблокированы.\nПричина: {reason}")
                except:
                    pass
            await session.commit()
            await message.answer(f"Пользователь {uid} {st}.")
        else:
            await message.answer("Пользователь не найден.")
    await state.clear()

# ---------- ОБРАБОТКА РАЗЖАЛОВАНИЙ ----------
@router.callback_query(F.data.startswith("unban_approve_"))
async def unban_approve(callback: CallbackQuery):
    req_id = int(callback.data.split("_")[2])
    async with AsyncSessionLocal() as session:
        req = await session.get(UnbanRequest, req_id)
        if not req or req.status != 'pending':
            await callback.answer("Заявка уже обработана")
            return
        req.status = 'approved'
        user = await session.get(User, req.user_id)
        if user:
            user.is_banned = False
            user.ban_reason = None
        await session.commit()
        await callback.bot.send_message(req.user_id, "✅ Ваша заявка на разжалование одобрена! Вы разблокированы.")
        await callback.message.edit_text(f"✅ Пользователь {req.user_id} разблокирован.")
    await callback.answer()

@router.callback_query(F.data.startswith("unban_reject_"))
async def unban_reject(callback: CallbackQuery):
    req_id = int(callback.data.split("_")[2])
    async with AsyncSessionLocal() as session:
        req = await session.get(UnbanRequest, req_id)
        if not req or req.status != 'pending':
            await callback.answer("Уже обработана")
            return
        req.status = 'rejected'
        await session.commit()
        await callback.bot.send_message(req.user_id, "❌ Ваша заявка на разжалование отклонена.")
        await callback.message.edit_text(f"❌ Заявка #{req_id} отклонена.")
    await callback.answer()

# ---------- ЗАМЕНЫ (АДМИН) ----------
@router.callback_query(F.data == "admin_replaces")
async def admin_replaces(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        reqs = (await session.execute(select(ReplaceRequest).where(ReplaceRequest.status == 'pending'))).scalars().all()
        if not reqs:
            await callback.message.edit_text("Нет активных заявок.")
            return
        for req in reqs:
            text = (f"Заявка #{req.id}\nПользователь: {req.user_id}\nТелефон: {req.phone_number or '-'}\nДата: {req.date_time or '-'}\nЖалоба: {req.complaint}")
            if req.photos:
                photo_ids = req.photos.split(',')
                if photo_ids:
                    media = [InputMediaPhoto(media=pid) for pid in photo_ids]
                    await callback.message.answer_media_group(media)
            await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
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
        await session.commit()
        try:
            await callback.bot.send_message(req.user_id, f"✅ Заявка на замену #{rid} одобрена. Ожидайте файл.")
        except Exception as e:
            await callback.answer(f"Ошибка: {e}")
    await callback.message.edit_reply_markup()
    await callback.answer("Одобрено")

@router.callback_query(F.data.startswith("reject_replace_"))
async def rej_replace(callback: CallbackQuery, state: FSMContext):
    rid = int(callback.data.split("_")[2])
    await callback.message.answer("Введите причину отказа (без бана):")
    await state.set_state(AdminReplaceReject.reason)
    await state.update_data(req_id=rid)
    await callback.answer()

@router.message(AdminReplaceReject.reason)
async def rej_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    rid = data.get('req_id')
    if not rid:
        await message.answer("Ошибка состояния.")
        await state.clear()
        return
    reason = message.text
    async with AsyncSessionLocal() as session:
        req = await session.get(ReplaceRequest, rid)
        if req and req.status == 'pending':
            req.status = 'rejected'
            req.admin_comment = reason
            await session.commit()
            try:
                await message.bot.send_message(req.user_id, f"❌ Заявка на замену #{rid} отклонена. Причина: {reason}")
                await message.answer("Отказ отправлен.")
            except:
                await message.answer("Не удалось уведомить.")
        else:
            await message.answer("Заявка уже обработана.")
    await state.clear()
