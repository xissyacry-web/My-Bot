from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    InputMediaPhoto, FSInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
from sqlalchemy import select, func, text
import os, sqlite3, shutil, sys

from database.database import AsyncSessionLocal
from database.models import (
    User, Product, Category, Promocode, UnbanRequest,
    Invoice, Purchase, ReplaceRequest
)
from config import ADMIN_IDS, VERSION, pe
from utils.states import *
from services.product_service import get_categories, get_products_by_category

router = Router()

def is_admin(uid): return uid in ADMIN_IDS

def back_kb(cb="admin_back"):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад", callback_data=cb)
    ]])

# ── MAIN ──────────────────────────────────────────────────────────────────────

@router.message(F.text == "/admin")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id): return
    from keyboards.inline import admin_main_kb

    await message.answer(
        f"{pe('crown')} <b>Админ-панель</b> {VERSION}",
        parse_mode="HTML",
        reply_markup=admin_main_keyboard()
    )

@router.callback_query(F.data == "admin_back")
async def back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    from keyboards.inline import admin_main_keyboard
    await callback.message.edit_text(
        f"{pe('crown')} <b>Админ-панель</b> {VERSION}",
        parse_mode="HTML",
        reply_markup=admin_main_keyboard()
    )
    await callback.answer()

# ── EXPORT / IMPORT ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_export")
async def export_db(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as session:
        await session.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
        await session.commit()
    try:
        await callback.message.answer_document(
            FSInputFile("bot.db"),
            caption=f"{pe('download')} <b>База данных</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.message.answer(f"Ошибка: {e}")
    await callback.answer()

@router.callback_query(F.data == "admin_import")
async def import_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text(
        f"{pe('warning')} Отправь файл <b>bot.db</b> — текущая БД сохранится в backup.db.",
        parse_mode="HTML",
        reply_markup=back_kb()
    )
    await state.set_state(AdminImport.file)
    await callback.answer()

@router.message(AdminImport.file, F.document)
async def import_file(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if not message.document.file_name.endswith(".db"):
        await message.answer("❌ Нужен .db файл")
        return
    file = await message.bot.get_file(message.document.file_id)
    temp = "bot.db.uploaded"
    await message.bot.download_file(file.file_path, temp)
    try:
        conn = sqlite3.connect(temp)
        conn.execute("SELECT 1 FROM users LIMIT 1")
        conn.close()
    except Exception:
        await message.answer("❌ Неверный файл БД.")
        os.remove(temp)
        return
    if os.path.exists("bot.db"):
        shutil.copy2("bot.db", "backup.db")
    os.replace(temp, "bot.db")
    await message.answer(f"{pe('check')} Импортировано. Перезапуск...", parse_mode="HTML")
    sys.exit(0)

# ── STATS ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_stats")
async def stats_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    b = InlineKeyboardBuilder()
    b.button(text="День",    callback_data="stats_day")
    b.button(text="7 дней",  callback_data="stats_week")
    b.button(text="30 дней", callback_data="stats_month")
    b.button(text="◀️ Назад", callback_data="admin_back")
    await callback.message.edit_text(f"{pe('chart')} Период:", parse_mode="HTML", reply_markup=b.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("stats_"))
async def stats_show(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    period = callback.data.split("_")[1]
    days = 1 if period == "day" else 7 if period == "week" else 30
    since = datetime.utcnow() - timedelta(days=days)
    async with AsyncSessionLocal() as session:
        new_u = (await session.execute(select(func.count(User.user_id)).where(User.registered_at >= since))).scalar()
        buys  = (await session.execute(select(func.count(Purchase.id)).where(Purchase.purchased_at >= since))).scalar()
        ref_c = (await session.execute(select(func.count(Invoice.id)).where(Invoice.created_at >= since, Invoice.status == 'paid'))).scalar()
        ref_s = (await session.execute(select(func.sum(Invoice.amount)).where(Invoice.created_at >= since, Invoice.status == 'paid'))).scalar() or 0.0
    t = (
        f"{pe('chart')} <b>Статистика за {days} дн.</b>\n\n"
        f"{pe('users')} Новых: {new_u}\n"
        f"{pe('cart')} Покупок: {buys}\n"
        f"{pe('wallet')} Пополнений: {ref_c} ({ref_s:.2f}$)"
    )
    await callback.message.edit_text(t, parse_mode="HTML", reply_markup=back_kb("admin_stats"))
    await callback.answer()

# ── VIEW LOGS ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_view_logs")
async def view_logs_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text(
        f"{pe('books')} Введи ID пользователя:", parse_mode="HTML", reply_markup=back_kb()
    )
    await state.set_state(AdminViewLogs.user_id)
    await callback.answer()

@router.message(AdminViewLogs.user_id)
async def view_logs_show(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        uid = int(message.text.strip())
    except Exception:
        await message.answer("Введи числовой ID.")
        return
    async with AsyncSessionLocal() as session:
        purchases = (await session.execute(
            select(Purchase).where(Purchase.user_id == uid)
            .order_by(Purchase.purchased_at.desc()).limit(20)
        )).scalars().all()
        if not purchases:
            await message.answer("Покупок нет.")
            await state.clear()
            return
        lines = [f"{pe('books')} <b>Покупки {uid}:</b>\n"]
        for p in purchases:
            product = await session.get(Product, p.product_id)
            pname = product.name if product else "удалён"
            lines.append(
                f"#{p.id} <b>{pname}</b> x{p.amount} — {p.price:.2f}$ — {p.purchased_at.strftime('%d.%m %H:%M')}"
            )
        await message.answer("\n".join(lines), parse_mode="HTML")
    await state.clear()

# ── BROADCAST ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text("Введи сообщение для рассылки:")
    await state.set_state(AdminBroadcast.message)
    await callback.answer()

@router.message(AdminBroadcast.message)
async def broadcast_exec(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    async with AsyncSessionLocal() as session:
        users = (await session.execute(select(User.user_id))).scalars().all()
    ok = fail = 0
    for uid in users:
        try:
            await message.bot.send_message(uid, message.text)
            ok += 1
        except Exception:
            fail += 1
    from services.log_service import log_broadcast
    await log_broadcast(message.bot, message.from_user.id, message.text, ok, fail)
    await message.answer(
        f"{pe('check')} Доставлено: {ok}, ошибок: {fail}.",
        parse_mode="HTML"
    )
    await state.clear()

# ── ADD PRODUCT ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_add_product")
async def add_prod(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session)
        if not cats:
            await callback.message.edit_text("Сначала создай категорию.", reply_markup=back_kb())
            return
        t = "Категории:\n" + "\n".join(f"{c.id}: {c.name}" for c in cats) + "\n\nВведи ID категории:"
    await callback.message.edit_text(t)
    await state.set_state(AdminAddProduct.category_id)
    await callback.answer()

@router.message(AdminAddProduct.category_id)
async def ap_cat(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: cat_id = int(message.text)
    except Exception:
        await message.answer("Число."); return
    async with AsyncSessionLocal() as session:
        if not await session.get(Category, cat_id):
            await message.answer("❌ Нет такой категории."); return
    await state.update_data(category_id=cat_id)
    await message.answer("Название товара:")
    await state.set_state(AdminAddProduct.name)

@router.message(AdminAddProduct.name)
async def ap_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(name=message.text)
    await message.answer("Описание (или «-» пропустить):")
    await state.set_state(AdminAddProduct.description)

@router.message(AdminAddProduct.description)
async def ap_desc(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(description=None if message.text == "-" else message.text)
    await message.answer("Цена ($):")
    await state.set_state(AdminAddProduct.price)

@router.message(AdminAddProduct.price)
async def ap_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: price = float(message.text.replace(',', '.'))
    except Exception:
        await message.answer("Число."); return
    await state.update_data(price=price)
    await message.answer("Количество (0 = безлимит):")
    await state.set_state(AdminAddProduct.quantity)

@router.message(AdminAddProduct.quantity)
async def ap_qty(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: qty = int(message.text)
    except Exception:
        await message.answer("Целое число."); return
    await state.update_data(quantity=qty)
    await message.answer("Контент (строки товара) или «-»:")
    await state.set_state(AdminAddProduct.content)

@router.message(AdminAddProduct.content)
async def ap_content(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(content=None if message.text == "-" else message.text)
    await message.answer("Файл для товара (или «-» пропустить):")
    await state.set_state(AdminAddProduct.file)

@router.message(AdminAddProduct.file)
async def ap_file(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    file_id = message.document.file_id if message.document else None
    async with AsyncSessionLocal() as session:
        product = Product(
            category_id=data['category_id'], name=data['name'],
            description=data.get('description'), price=data['price'],
            quantity=data.get('quantity', 0), content=data.get('content'), file_id=file_id
        )
        session.add(product)
        await session.commit()
    await message.answer(f"{pe('check')} Товар «{data['name']}» добавлен.", parse_mode="HTML")
    await state.clear()

# ── BULK TXT ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_bulk_product")
async def bulk_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session)
        if not cats:
            await callback.message.edit_text("Нет категорий.", reply_markup=back_kb()); return
        t = "Категории:\n" + "\n".join(f"{c.id}: {c.name}" for c in cats) + "\n\nВведи ID категории:"
    await callback.message.edit_text(t)
    await state.set_state(AdminBulkProduct.category_id)
    await callback.answer()

@router.message(AdminBulkProduct.category_id)
async def bulk_cat(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: cat_id = int(message.text)
    except Exception:
        await message.answer("Число."); return
    async with AsyncSessionLocal() as session:
        products = await get_products_by_category(session, cat_id)
        if not products:
            await message.answer("Нет товаров в категории. Сначала добавь товар."); return
        t = "Товары:\n" + "\n".join(f"{p.id}: {p.name}" for p in products) + "\n\nВведи ID товара:"
    await state.update_data(category_id=cat_id)
    await message.answer(t)
    await state.set_state(AdminBulkProduct.product_id)

@router.message(AdminBulkProduct.product_id)
async def bulk_prod(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: prod_id = int(message.text)
    except Exception:
        await message.answer("Число."); return
    async with AsyncSessionLocal() as session:
        if not await session.get(Product, prod_id):
            await message.answer("❌ Нет такого товара."); return
    await state.update_data(product_id=prod_id)
    await message.answer(
        f"{pe('download')} Отправь .txt файл.\nКаждая строка = один товар.",
        parse_mode="HTML"
    )
    await state.set_state(AdminBulkProduct.file)

@router.message(AdminBulkProduct.file, F.document)
async def bulk_file(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if not message.document.file_name.endswith(".txt"):
        await message.answer("❌ Нужен .txt файл."); return
    data = await state.get_data()
    file = await message.bot.get_file(message.document.file_id)
    downloaded = await message.bot.download_file(file.file_path)
    raw = downloaded.read().decode('utf-8', errors='replace')
    new_lines = [l.strip() for l in raw.split('\n') if l.strip()]
    if not new_lines:
        await message.answer("Файл пустой."); await state.clear(); return
    async with AsyncSessionLocal() as session:
        product = await session.get(Product, data['product_id'])
        existing = [l for l in (product.content or "").split('\n') if l.strip()]
        product.content = '\n'.join(existing + new_lines)
        product.quantity = len([l for l in product.content.split('\n') if l.strip()])
        await session.commit()
        total = product.quantity
    await message.answer(
        f"{pe('check')} Добавлено {len(new_lines)} строк. Всего: {total}.",
        parse_mode="HTML"
    )
    await state.clear()

# ── EDIT DESCRIPTION ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_edit_desc")
async def edit_desc_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session)
        if not cats:
            await callback.message.edit_text("Нет категорий.", reply_markup=back_kb()); return
        t = "Категории:\n" + "\n".join(f"{c.id}: {c.name}" for c in cats) + "\n\nВведи ID категории:"
    await callback.message.edit_text(t)
    await state.set_state(AdminEditDesc.category_id)
    await callback.answer()

@router.message(AdminEditDesc.category_id)
async def edit_desc_cat(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: cat_id = int(message.text)
    except Exception:
        await message.answer("Число."); return
    async with AsyncSessionLocal() as session:
        products = await get_products_by_category(session, cat_id)
        if not products:
            await message.answer("Нет товаров."); return
        t = "Товары:\n" + "\n".join(f"{p.id}: {p.name} | {(p.description or '—')[:40]}" for p in products)
        t += "\n\nВведи ID товара:"
    await state.update_data(category_id=cat_id)
    await message.answer(t)
    await state.set_state(AdminEditDesc.product_id)

@router.message(AdminEditDesc.product_id)
async def edit_desc_prod(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: prod_id = int(message.text)
    except Exception:
        await message.answer("Число."); return
    await state.update_data(product_id=prod_id)
    await message.answer("Введи новое описание:")
    await state.set_state(AdminEditDesc.new_desc)

@router.message(AdminEditDesc.new_desc)
async def edit_desc_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        product = await session.get(Product, data['product_id'])
        if not product:
            await message.answer("Товар не найден."); await state.clear(); return
        product.description = message.text
        await session.commit()
    await message.answer(f"{pe('check')} Описание обновлено.", parse_mode="HTML")
    await state.clear()

# ── REFILL ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_refill_product")
async def refill_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session)
        t = "Категории:\n" + "\n".join(f"{c.id}: {c.name}" for c in cats) + "\n\nВведи ID категории:"
    await callback.message.edit_text(t)
    await state.set_state(AdminRefillProduct.category_id)
    await callback.answer()

@router.message(AdminRefillProduct.category_id)
async def refill_cat(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: cat_id = int(message.text)
    except Exception:
        await message.answer("Число."); return
    async with AsyncSessionLocal() as session:
        products = await get_products_by_category(session, cat_id)
        t = "Товары:\n" + "\n".join(f"{p.id}: {p.name} ({p.quantity} шт.)" for p in products) + "\n\nВведи ID товара:"
    await state.update_data(category_id=cat_id)
    await message.answer(t)
    await state.set_state(AdminRefillProduct.product_id)

@router.message(AdminRefillProduct.product_id)
async def refill_prod(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: prod_id = int(message.text)
    except Exception:
        await message.answer("Число."); return
    await state.update_data(product_id=prod_id)
    await message.answer("Введи новые строки (каждая с новой строки):")
    await state.set_state(AdminRefillProduct.content)

@router.message(AdminRefillProduct.content)
async def refill_content(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    new_lines = [l.strip() for l in message.text.split('\n') if l.strip()]
    async with AsyncSessionLocal() as session:
        product = await session.get(Product, data['product_id'])
        existing = [l for l in (product.content or "").split('\n') if l.strip()]
        product.content = '\n'.join(existing + new_lines)
        product.quantity = len([l for l in product.content.split('\n') if l.strip()])
        await session.commit()
        total = product.quantity
    await message.answer(
        f"{pe('check')} +{len(new_lines)} строк. Итого: {total}.",
        parse_mode="HTML"
    )
    await state.clear()

# ── DELETE LINES ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_delete_lines")
async def del_lines_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session)
        t = "Категории:\n" + "\n".join(f"{c.id}: {c.name}" for c in cats) + "\n\nВведи ID категории:"
    await callback.message.edit_text(t)
    await state.set_state(AdminDeleteLines.category_id)
    await callback.answer()

@router.message(AdminDeleteLines.category_id)
async def dl_cat(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: cat_id = int(message.text)
    except Exception:
        await message.answer("Число."); return
    async with AsyncSessionLocal() as session:
        products = await get_products_by_category(session, cat_id)
        t = "Товары:\n" + "\n".join(f"{p.id}: {p.name} ({p.quantity} шт.)" for p in products) + "\n\nВведи ID товара:"
    await state.update_data(category_id=cat_id)
    await message.answer(t)
    await state.set_state(AdminDeleteLines.product_id)

@router.message(AdminDeleteLines.product_id)
async def dl_prod(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: prod_id = int(message.text)
    except Exception:
        await message.answer("Число."); return
    async with AsyncSessionLocal() as session:
        product = await session.get(Product, prod_id)
        if not product or not product.content:
            await message.answer("Нет контента."); return
        lines = [l for l in product.content.split('\n') if l.strip()]
        preview = "\n".join(f"{i+1}: {l}" for i, l in enumerate(lines[:20]))
        if len(lines) > 20: preview += f"\n... и ещё {len(lines)-20}"
    await state.update_data(product_id=prod_id)
    await message.answer(
        f"📋 Строки ({len(lines)} шт.):\n\n<code>{preview}</code>\n\n"
        "Введи номера через запятую для удаления\n"
        "или <b>«всё кроме 1,2,3»</b> чтобы оставить только их.",
        parse_mode="HTML"
    )
    await state.set_state(AdminDeleteLines.lines)

@router.message(AdminDeleteLines.lines)
async def dl_execute(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    inp = message.text.strip()
    async with AsyncSessionLocal() as session:
        product = await session.get(Product, data['product_id'])
        lines = [l for l in product.content.split('\n') if l.strip()]
        keep_mode = inp.lower().startswith("всё кроме")
        if keep_mode:
            nums_str = inp.lower().replace("всё кроме", "").strip()
            try: keep = {int(n.strip()) for n in nums_str.split(',')}
            except Exception:
                await message.answer("Неверный формат."); return
            new_lines = [l for i, l in enumerate(lines, 1) if i in keep]
        else:
            try: remove = {int(n.strip()) for n in inp.split(',')}
            except Exception:
                await message.answer("Введи номера через запятую."); return
            new_lines = [l for i, l in enumerate(lines, 1) if i not in remove]
        product.content = '\n'.join(new_lines)
        product.quantity = len(new_lines)
        await session.commit()
    await message.answer(
        f"{pe('check')} Готово. Осталось: {len(new_lines)} строк.",
        parse_mode="HTML"
    )
    await state.clear()

# ── ADD CATEGORY ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_add_category")
async def add_cat_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text("Название категории:")
    await state.set_state(AdminAddCategory.name)
    await callback.answer()

@router.message(AdminAddCategory.name)
async def add_cat_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(name=message.text)
    await message.answer("ID родительской категории (или «0» — корневая):")
    await state.set_state(AdminAddCategory.parent_id)

@router.message(AdminAddCategory.parent_id)
async def add_cat_parent(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: parent_id = int(message.text)
    except Exception:
        await message.answer("Число."); return
    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        cat = Category(name=data['name'], parent_id=parent_id if parent_id != 0 else None)
        session.add(cat)
        await session.commit()
    await message.answer(f"{pe('check')} Категория «{data['name']}» создана.", parse_mode="HTML")
    await state.clear()

# ── DELETE PRODUCT ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_delete_product")
async def del_prod_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session)
        t = "Категории:\n" + "\n".join(f"{c.id}: {c.name}" for c in cats) + "\n\nВведи ID категории:"
    await callback.message.edit_text(t)
    await state.set_state(AdminDeleteProduct.category_id)
    await callback.answer()

@router.message(AdminDeleteProduct.category_id)
async def dp_cat(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: cat_id = int(message.text)
    except Exception:
        await message.answer("Число."); return
    async with AsyncSessionLocal() as session:
        products = await get_products_by_category(session, cat_id)
        t = "Товары:\n" + "\n".join(f"{p.id}: {p.name}" for p in products) + "\n\nВведи ID товара:"
    await state.update_data(category_id=cat_id)
    await message.answer(t)
    await state.set_state(AdminDeleteProduct.product_id)

@router.message(AdminDeleteProduct.product_id)
async def dp_exec(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: prod_id = int(message.text)
    except Exception:
        await message.answer("Число."); return
    async with AsyncSessionLocal() as session:
        product = await session.get(Product, prod_id)
        if not product:
            await message.answer("❌ Не найдено."); return
        name = product.name
        await session.delete(product)
        await session.commit()
    await message.answer(f"{pe('check')} «{name}» удалён.", parse_mode="HTML")
    await state.clear()

# ── DELETE CATEGORY ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_delete_category")
async def del_cat_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session)
        t = "Категории:\n" + "\n".join(f"{c.id}: {c.name}" for c in cats) + "\n\nВведи ID для удаления:"
    await callback.message.edit_text(t)
    await state.set_state(AdminDeleteCategory.category_id)
    await callback.answer()

@router.message(AdminDeleteCategory.category_id)
async def dc_exec(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: cat_id = int(message.text)
    except Exception:
        await message.answer("Число."); return
    async with AsyncSessionLocal() as session:
        cat = await session.get(Category, cat_id)
        if not cat:
            await message.answer("❌ Нет такой категории."); return
        name = cat.name
        await session.delete(cat)
        await session.commit()
    await message.answer(f"{pe('check')} Категория «{name}» удалена.", parse_mode="HTML")
    await state.clear()

# ── PROMOCODES ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_promocodes")
async def promos_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    from keyboards.inline import admin_promocodes_keyboard
    await callback.message.edit_text(
        f"{pe('gift')} <b>Промокоды:</b>",
        parse_mode="HTML",
        reply_markup=admin_promocodes_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "promo_list")
async def promo_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as session:
        promos = (await session.execute(select(Promocode))).scalars().all()
    if not promos:
        await callback.answer("Промокодов нет.", show_alert=True); return
    lines = [f"{pe('gift')} <b>Промокоды:</b>\n"]
    for p in promos:
        s = "✅" if p.is_active else "❌"
        exp = p.expires_at.strftime('%d.%m.%Y') if p.expires_at else "∞"
        lines.append(f"{s} <code>{p.code}</code> | +{p.bonus_amount}$ | {p.used_count}/{p.max_activations or '∞'} | до {exp}")
    await callback.message.answer("\n".join(lines), parse_mode="HTML", reply_markup=back_kb("admin_promocodes"))
    await callback.answer()

@router.callback_query(F.data == "promo_add")
async def promo_add_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text("Код промокода:")
    await state.set_state(AdminPromoAdd.code)
    await callback.answer()

@router.message(AdminPromoAdd.code)
async def pa_code(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(code=message.text.strip())
    await message.answer("Сумма бонуса ($):")
    await state.set_state(AdminPromoAdd.amount)

@router.message(AdminPromoAdd.amount)
async def pa_amount(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: amt = float(message.text.replace(',', '.'))
    except Exception:
        await message.answer("Число."); return
    await state.update_data(amount=amt)
    await message.answer("Макс. активаций (0 = безлимит):")
    await state.set_state(AdminPromoAdd.max_activations)

@router.message(AdminPromoAdd.max_activations)
async def pa_max(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: mx = int(message.text)
    except Exception:
        await message.answer("Число."); return
    await state.update_data(max_activations=None if mx == 0 else mx)
    await message.answer("Срок в днях (0 = бессрочно):")
    await state.set_state(AdminPromoAdd.expires_days)

@router.message(AdminPromoAdd.expires_days)
async def pa_expires(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: days = int(message.text)
    except Exception:
        await message.answer("Число."); return
    data = await state.get_data()
    expires = datetime.utcnow() + timedelta(days=days) if days > 0 else None
    async with AsyncSessionLocal() as session:
        session.add(Promocode(
            code=data['code'], bonus_amount=data['amount'],
            max_activations=data.get('max_activations'), expires_at=expires
        ))
        await session.commit()
    await message.answer(f"{pe('check')} Промокод «{data['code']}» создан.", parse_mode="HTML")
    await state.clear()

@router.callback_query(F.data == "promo_delete")
async def promo_del_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text("Код промокода для удаления:")
    await state.set_state(AdminPromoDelete.code)
    await callback.answer()

@router.message(AdminPromoDelete.code)
async def promo_del_exec(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    code = message.text.strip()
    async with AsyncSessionLocal() as session:
        promo = await session.get(Promocode, code)
        if not promo:
            await message.answer("❌ Не найдено."); await state.clear(); return
        await session.delete(promo)
        await session.commit()
    await message.answer(f"{pe('check')} «{code}» удалён.", parse_mode="HTML")
    await state.clear()

# ── USERS ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_users_menu")
async def users_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    from keyboards.inline import admin_users_keyboard
    await callback.message.edit_text(
        f"{pe('users')} <b>Пользователи:</b>",
        parse_mode="HTML",
        reply_markup=admin_users_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "user_search")
async def user_search_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text(f"{pe('search')} Введи ID:", parse_mode="HTML")
    await state.set_state(AdminUserSearch.user_id)
    await callback.answer()

@router.message(AdminUserSearch.user_id)
async def user_search_show(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: uid = int(message.text.strip())
    except Exception:
        await message.answer("Число."); return
    async with AsyncSessionLocal() as session:
        user = await session.get(User, uid)
        if not user:
            await message.answer("❌ Не найден."); await state.clear(); return
        buys = len((await session.execute(select(Purchase).where(Purchase.user_id == uid))).scalars().all())
        t = (
            f"{pe('user')} ID: <code>{user.user_id}</code>\n"
            f"Username: @{user.username or '—'}\n"
            f"{pe('wallet')} Баланс: {user.balance:.2f}$\n"
            f"{pe('briefcase')} Покупок: {buys}\n"
            f"{pe('ban') if user.is_banned else pe('check')} Бан: {'да — ' + (user.ban_reason or '—') if user.is_banned else 'нет'}\n"
            f"{pe('clock')} Рег.: {user.registered_at.strftime('%d.%m.%Y')}"
        )
    await message.answer(t, parse_mode="HTML")
    await state.clear()

@router.callback_query(F.data == "user_balance")
async def user_balance_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text(f"{pe('wallet')} Введи ID:", parse_mode="HTML")
    await state.set_state(AdminUserBalance.user_id)
    await callback.answer()

@router.message(AdminUserBalance.user_id)
async def ub_get_uid(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: uid = int(message.text)
    except Exception:
        await message.answer("Число."); return
    async with AsyncSessionLocal() as session:
        user = await session.get(User, uid)
        if not user:
            await message.answer("❌ Не найден."); await state.clear(); return
    await state.update_data(user_id=uid)
    await message.answer(f"Баланс: {user.balance:.2f}$\nВведи новое значение (+10, -5 или просто число):")
    await state.set_state(AdminUserBalance.amount)

@router.message(AdminUserBalance.amount)
async def ub_set(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    txt = message.text.strip()
    async with AsyncSessionLocal() as session:
        user = await session.get(User, data['user_id'])
        try:
            if txt.startswith('+'): user.balance += float(txt[1:])
            elif txt.startswith('-'): user.balance -= float(txt[1:])
            else: user.balance = float(txt)
        except Exception:
            await message.answer("Неверный формат."); return
        await session.commit()
        await message.answer(f"{pe('check')} Баланс: {user.balance:.2f}$", parse_mode="HTML")
    await state.clear()

@router.callback_query(F.data == "user_ban")
async def user_ban_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text(f"{pe('ban')} Введи ID (бан/разбан):", parse_mode="HTML")
    await state.set_state(AdminUserBan.user_id)
    await callback.answer()

@router.message(AdminUserBan.user_id)
async def ban_get_uid(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: uid = int(message.text)
    except Exception:
        await message.answer("Число."); return
    async with AsyncSessionLocal() as session:
        user = await session.get(User, uid)
        if not user:
            await message.answer("❌ Не найден."); await state.clear(); return
        if user.is_banned:
            user.is_banned = False
            user.ban_reason = None
            await session.commit()
            await message.answer(f"{pe('check')} {uid} разбанен.", parse_mode="HTML")
            await state.clear(); return
    await state.update_data(user_id=uid)
    await message.answer("Причина бана:")
    await state.set_state(AdminUserBan.reason)

@router.message(AdminUserBan.reason)
async def ban_exec(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        user = await session.get(User, data['user_id'])
        user.is_banned = True
        user.ban_reason = message.text
        await session.commit()
    try:
        await message.bot.send_message(
            data['user_id'],
            f"{pe('ban')} Вы заблокированы.\nПричина: {message.text}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Разжаловать", callback_data="unban_request")
            ]])
        )
    except Exception: pass
    await message.answer(f"{pe('check')} {data['user_id']} заблокирован.", parse_mode="HTML")
    await state.clear()

# ── REPLACE REQUESTS ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_replaces")
async def admin_replaces(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as session:
        reqs = (await session.execute(
            select(ReplaceRequest).where(ReplaceRequest.status == 'pending').limit(20)
        )).scalars().all()
    if not reqs:
        await callback.answer("Заявок нет.", show_alert=True); return
    lines = [f"{pe('hammer')} <b>Заявки на замену:</b>\n"]
    for r in reqs:
        lines.append(f"#{r.id} | {r.user_id} | {r.created_at.strftime('%d.%m %H:%M')}")
    await callback.message.answer("\n".join(lines), parse_mode="HTML", reply_markup=back_kb())
    await callback.answer()

@router.callback_query(F.data.startswith("replace_approve_"))
async def replace_approve(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    req_id = int(callback.data.split("_")[2])
    await state.update_data(req_id=req_id)
    await callback.message.answer("Сообщение для пользователя (одобрение):")
    await state.set_state(AdminReplaceApprove.message)
    await callback.answer()

@router.message(AdminReplaceApprove.message)
async def replace_approve_msg(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        req = await session.get(ReplaceRequest, data['req_id'])
        if req:
            req.status = 'approved'
            req.admin_comment = message.text
            await session.commit()
            try: await message.bot.send_message(req.user_id, f"{pe('check')} Заявка #{req.id} одобрена.\n{message.text}", parse_mode="HTML")
            except Exception: pass
    await message.answer(f"{pe('check')} Одобрено.", parse_mode="HTML")
    await state.clear()

@router.callback_query(F.data.startswith("replace_reject_"))
async def replace_reject(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    req_id = int(callback.data.split("_")[2])
    await state.update_data(req_id=req_id)
    await callback.message.answer("Причина отказа:")
    await state.set_state(AdminReplaceReject.reason)
    await callback.answer()

@router.message(AdminReplaceReject.reason)
async def replace_reject_msg(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        req = await session.get(ReplaceRequest, data['req_id'])
        if req:
            req.status = 'rejected'
            req.admin_comment = message.text
            await session.commit()
            try: await message.bot.send_message(req.user_id, f"{pe('ban')} Заявка #{req.id} отклонена.\n{message.text}", parse_mode="HTML")
            except Exception: pass
    await message.answer(f"{pe('check')} Отклонено.", parse_mode="HTML")
    await state.clear()

# ── UNBAN ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("unban_approve_"))
async def unban_approve(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    req_id = int(callback.data.split("_")[2])
    async with AsyncSessionLocal() as session:
        req = await session.get(UnbanRequest, req_id)
        if req:
            req.status = 'approved'
            user = await session.get(User, req.user_id)
            if user: user.is_banned = False; user.ban_reason = None
            await session.commit()
            try: await callback.bot.send_message(req.user_id, f"{pe('unlock')} Вы разблокированы.", parse_mode="HTML")
            except Exception: pass
    await callback.message.answer(f"{pe('check')} Разблокирован.", parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("unban_reject_"))
async def unban_reject(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    req_id = int(callback.data.split("_")[2])
    async with AsyncSessionLocal() as session:
        req = await session.get(UnbanRequest, req_id)
        if req:
            req.status = 'rejected'
            await session.commit()
            try: await callback.bot.send_message(req.user_id, f"{pe('ban')} В разблокировке отказано.", parse_mode="HTML")
            except Exception: pass
    await callback.message.answer(f"{pe('check')} Отклонено.", parse_mode="HTML")
    await callback.answer()
