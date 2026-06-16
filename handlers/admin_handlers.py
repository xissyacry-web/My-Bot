from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
from sqlalchemy import select, func, text
import os, sqlite3, shutil, sys

from database.database import AsyncSessionLocal
from database.models import User, Product, Category, Promocode, UnbanRequest, Invoice, Purchase, ReplaceRequest, ScheduledBroadcast, StockNotify
from config import ADMIN_IDS, VERSION, pe, pe_coin, pe_num
from keyboards.kb import (
    admin_main as admin_main_kb,
    admin_back as admin_back_kb,
    admin_promos as admin_promos_kb,
    admin_users as admin_users_kb,
    broadcast_timing as broadcast_timing_kb,
    unban_action as unban_action_kb,
    to_main, ibtn, banned_kb, replace_action,
)


from utils.states import *
from services.product_service import get_categories, get_products_by_category

router = Router()
def is_admin(uid): return uid in ADMIN_IDS

@router.callback_query(F.data == "admin_noop")
async def admin_noop(callback: CallbackQuery):
    await callback.answer()

@router.callback_query(F.data == "admin_unbans")
async def admin_unbans(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        from database.models import UnbanRequest
        reqs = (await s.execute(select(UnbanRequest).where(UnbanRequest.status == 'pending').limit(20))).scalars().all()
    if not reqs:
        await callback.answer("Заявок нет.", show_alert=True); return
    lines = ["🔓 <b>Заявки на разблокировку:</b>\n"]
    for r in reqs:
        lines.append(f"#{r.id} | {r.user_id} | {r.created_at.strftime('%d.%m %H:%M')}")
    await callback.message.answer("\n".join(lines), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "admin_scheduled")
async def admin_scheduled(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        items = (await s.execute(
            select(ScheduledBroadcast).where(ScheduledBroadcast.sent == False)
        )).scalars().all()
    if not items:
        await callback.answer("Нет запланированных.", show_alert=True); return
    lines = ["📅 <b>Запланированные рассылки:</b>\n"]
    for i in items:
        lines.append(f"#{i.id} · {i.send_at.strftime('%d.%m.%Y %H:%M')}\n<i>{i.text[:50]}</i>")
    await callback.message.answer("\n\n".join(lines), parse_mode="HTML")
    await callback.answer()


def back_kb(cb="admin_back"):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data=cb)]])

@router.message(F.text == "/admin")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id): return
    await message.answer(f"{pe('crown')} <b>Админ {VERSION}</b>", parse_mode="HTML", reply_markup=admin_main_kb())

@router.callback_query(F.data == "admin_back")
async def adm_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(f"{pe('crown')} <b>Админ {VERSION}</b>", parse_mode="HTML", reply_markup=admin_main_kb())
    await callback.answer()

@router.callback_query(F.data == "admin_export")
async def export_db(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        await s.execute(text("PRAGMA wal_checkpoint(TRUNCATE)")); await s.commit()
    try:
        await callback.message.answer_document(FSInputFile("bot.db"), caption=f"{pe('download')} <b>БД</b>", parse_mode="HTML")
    except Exception as e:
        await callback.message.answer(f"Ошибка: {e}")
    await callback.answer()

@router.callback_query(F.data == "admin_import")
async def import_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text(f"{pe('warning')} Отправь файл <b>bot.db</b>", parse_mode="HTML", reply_markup=back_kb())
    await state.set_state(ImportDB.file); await callback.answer()

@router.message(ImportDB.file, F.document)
async def import_file(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if not message.document.file_name.endswith(".db"):
        await message.answer("Нужен .db файл"); return
    file = await message.bot.get_file(message.document.file_id)
    temp = "bot.db.tmp"
    await message.bot.download_file(file.file_path, temp)
    try:
        conn = sqlite3.connect(temp); conn.execute("SELECT 1 FROM users LIMIT 1"); conn.close()
    except Exception:
        await message.answer("Неверный файл."); os.remove(temp); return
    if os.path.exists("bot.db"): shutil.copy2("bot.db", "backup.db")
    os.replace(temp, "bot.db")
    await message.answer(f"{pe('check')} Импортировано. Перезапуск...", parse_mode="HTML")
    sys.exit(0)

@router.callback_query(F.data == "admin_stats")
async def stats_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    b = InlineKeyboardBuilder()
    b.button(text="День", callback_data="stats_day")
    b.button(text="7 дней", callback_data="stats_week")
    b.button(text="30 дней", callback_data="stats_month")
    b.button(text="◀️ Назад", callback_data="admin_back")
    await callback.message.edit_text(f"{pe('chart')} Период:", parse_mode="HTML", reply_markup=b.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("stats_"))
async def stats_show(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    days = {"day": 1, "week": 7, "month": 30}[callback.data.split("_")[1]]
    since = datetime.utcnow() - timedelta(days=days)
    async with AsyncSessionLocal() as s:
        new_u = (await s.execute(select(func.count(User.user_id)).where(User.registered_at >= since))).scalar()
        buys  = (await s.execute(select(func.count(Purchase.id)).where(Purchase.purchased_at >= since))).scalar()
        rev   = (await s.execute(select(func.sum(Purchase.price)).where(Purchase.purchased_at >= since))).scalar() or 0
        ref_c = (await s.execute(select(func.count(Invoice.id)).where(Invoice.created_at >= since, Invoice.status == 'paid'))).scalar()
        ref_s = (await s.execute(select(func.sum(Invoice.amount)).where(Invoice.created_at >= since, Invoice.status == 'paid'))).scalar() or 0
        total_u = (await s.execute(select(func.count(User.user_id)))).scalar()
    await callback.message.edit_text(
        f"{pe('chart')} <b>Статистика за {days} дн.</b>\n\n"
        f"{pe('users')} Новых: {new_u} / всего {total_u}\n"
        f"{pe('cart')} Покупок: {buys} ({rev:.2f}$)\n"
        f"{pe('wallet')} Пополнений: {ref_c} ({ref_s:.2f}$)",
        parse_mode="HTML", reply_markup=back_kb("admin_stats")
    )
    await callback.answer()

@router.callback_query(F.data == "admin_top_buyers")
async def top_buyers(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(User.user_id, User.username, User.total_spent).order_by(User.total_spent.desc()).limit(10)
        )).all()
    medals = ["🥇","🥈","🥉"] + ["🏅"]*7
    lines = [f"{pe('crown')} <b>Топ покупателей</b>\n"]
    for i, (uid, uname, spent) in enumerate(rows):
        lines.append(f"{medals[i]} {'@'+uname if uname else 'id:'+str(uid)} — {spent:.2f}$")
    await callback.message.answer("\n".join(lines), parse_mode="HTML", reply_markup=back_kb())
    await callback.answer()

@router.callback_query(F.data == "admin_view_logs")
async def view_logs_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text(f"{pe('books')} ID пользователя:", parse_mode="HTML", reply_markup=back_kb())
    await state.set_state(ViewLogs.uid); await callback.answer()

@router.message(ViewLogs.uid)
async def view_logs_show(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: uid = int(message.text.strip())
    except Exception: await message.answer("Число."); return
    async with AsyncSessionLocal() as s:
        purchases = (await s.execute(
            select(Purchase).where(Purchase.user_id == uid).order_by(Purchase.purchased_at.desc()).limit(20)
        )).scalars().all()
        if not purchases: await message.answer("Покупок нет."); await state.clear(); return
        lines = [f"{pe('books')} <b>Покупки {uid}:</b>\n"]
        for p in purchases:
            prod = await s.get(Product, p.product_id)
            pname = prod.name if prod else "удалён"
            lines.append(f"#{p.id} <b>{pname}</b> ×{p.amount} — {p.price:.2f}$ — {p.purchased_at.strftime('%d.%m %H:%M')}")
        await message.answer("\n".join(lines), parse_mode="HTML")
    await state.clear()

@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text("Введи текст рассылки:")
    await state.set_state(Broadcast.text); await callback.answer()

@router.message(Broadcast.text)
async def broadcast_timing(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(text=message.text)
    await message.answer("Когда отправить?", reply_markup=broadcast_timing_kb())
    await state.set_state(Broadcast.schedule)

@router.callback_query(Broadcast.schedule, F.data == "broadcast_now")
async def broadcast_now(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    data = await state.get_data(); await state.clear()
    async with AsyncSessionLocal() as s:
        users = (await s.execute(select(User.user_id))).scalars().all()
    ok = fail = 0
    for uid in users:
        try: await callback.bot.send_message(uid, data['text']); ok += 1
        except Exception: fail += 1
    from services.log_service import log_broadcast
    await log_broadcast(callback.bot, callback.from_user.id, data['text'], ok, fail)
    await callback.message.answer(f"{pe('check')} Доставлено: {ok}, ошибок: {fail}.", parse_mode="HTML")
    await callback.answer()

@router.callback_query(Broadcast.schedule, F.data == "broadcast_schedule")
async def broadcast_schedule_prompt(callback: CallbackQuery):
    await callback.message.answer("Дата и время: <b>ДД.ММ.ГГГГ ЧЧ:ММ</b>", parse_mode="HTML")
    await callback.answer()

@router.message(Broadcast.schedule)
async def broadcast_schedule_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: send_at = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
    except Exception: await message.answer("Формат: 25.12.2025 18:00"); return
    data = await state.get_data()
    async with AsyncSessionLocal() as s:
        s.add(ScheduledBroadcast(text=data['text'], send_at=send_at)); await s.commit()
    await message.answer(f"{pe('check')} Запланировано на {send_at.strftime('%d.%m.%Y %H:%M')}", parse_mode="HTML")
    await state.clear()

@router.callback_query(F.data == "admin_add_product")
async def add_prod(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        cats = await get_categories(s)
        if not cats: await callback.message.edit_text("Нет категорий.", reply_markup=back_kb()); return
        t = "Категории:\n" + "\n".join(f"{c.id}: {c.name}" for c in cats) + "\n\nID категории:"
    await callback.message.edit_text(t); await state.set_state(AddProduct.cat_id); await callback.answer()

@router.message(AddProduct.cat_id)
async def ap_cat(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: cid = int(message.text)
    except Exception: await message.answer("Число."); return
    async with AsyncSessionLocal() as s:
        if not await s.get(Category, cid): await message.answer("Нет такой категории."); return
    await state.update_data(category_id=cid); await message.answer("Название:"); await state.set_state(AddProduct.name)

@router.message(AddProduct.name)
async def ap_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(name=message.text); await message.answer("Описание (или «-»):"); await state.set_state(AddProduct.desc)

@router.message(AddProduct.desc)
async def ap_desc(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(description=None if message.text=="-" else message.text)
    await message.answer("Цена ($):"); await state.set_state(AddProduct.price)

@router.message(AddProduct.price)
async def ap_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: p = float(message.text.replace(',','.'))
    except Exception: await message.answer("Число."); return
    await state.update_data(price=p); await message.answer("Кол-во (0=∞):"); await state.set_state(AddProduct.qty)

@router.message(AddProduct.qty)
async def ap_qty(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: q = int(message.text)
    except Exception: await message.answer("Целое."); return
    await state.update_data(quantity=q); await message.answer("Контент строками (или «-»):"); await state.set_state(AddProduct.content)

@router.message(AddProduct.content)
async def ap_content(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(content=None if message.text=="-" else message.text)
    await message.answer("Файл (или «-»):"); await state.set_state(AddProduct.file)

@router.message(AddProduct.file)
async def ap_file(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    fid = message.document.file_id if message.document else None
    async with AsyncSessionLocal() as s:
        s.add(Product(category_id=data['category_id'], name=data['name'], description=data.get('description'),
                      price=data['price'], quantity=data.get('quantity',0), content=data.get('content'), file_id=fid))
        await s.commit()
    await message.answer(f"{pe('check')} «{data['name']}» добавлен.", parse_mode="HTML"); await state.clear()

@router.callback_query(F.data == "admin_bulk_product")
async def bulk_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        cats = await get_categories(s)
        if not cats: await callback.message.edit_text("Нет категорий.", reply_markup=back_kb()); return
        t = "Категории:\n" + "\n".join(f"{c.id}: {c.name}" for c in cats) + "\n\nID категории:"
    await callback.message.edit_text(t); await state.set_state(BulkTxt.category_id); await callback.answer()

@router.message(BulkTxt.category_id)
async def bulk_cat(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: cid = int(message.text)
    except Exception: await message.answer("Число."); return
    async with AsyncSessionLocal() as s:
        prods = await get_products_by_category(s, cid)
        if not prods: await message.answer("Нет товаров в категории."); return
        t = "Товары:\n" + "\n".join(f"{p.id}: {p.name}" for p in prods) + "\n\nID товара:"
    await state.update_data(category_id=cid); await message.answer(t); await state.set_state(BulkTxt.product_id)

@router.message(BulkTxt.product_id)
async def bulk_prod(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: pid = int(message.text)
    except Exception: await message.answer("Число."); return
    await state.update_data(product_id=pid)
    await message.answer(f"{pe('download')} Отправь .txt (каждая строка = товар):", parse_mode="HTML")
    await state.set_state(BulkTxt.file)

@router.message(BulkTxt.file, F.document)
async def bulk_file(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if not message.document.file_name.endswith(".txt"):
        await message.answer("Нужен .txt"); return
    data = await state.get_data()
    f = await message.bot.get_file(message.document.file_id)
    raw = (await message.bot.download_file(f.file_path)).read().decode('utf-8', errors='replace')
    new_lines = [l.strip() for l in raw.split('\n') if l.strip()]
    if not new_lines: await message.answer("Файл пустой."); await state.clear(); return
    async with AsyncSessionLocal() as s:
        prod = await s.get(Product, data['product_id'])
        existing = [l for l in (prod.content or "").split('\n') if l.strip()]
        prod.content = '\n'.join(existing + new_lines)
        prod.quantity = len([l for l in prod.content.split('\n') if l.strip()])
        prod.is_available = True
        total = prod.quantity
        notifies = (await s.execute(select(StockNotify).where(StockNotify.product_id == prod.id))).scalars().all()
        for n in notifies:
            try: await message.bot.send_message(n.user_id, f"{pe('bell')} Товар <b>{prod.name}</b> снова в наличии!", parse_mode="HTML")
            except Exception: pass
            await s.delete(n)
        await s.commit()
    await message.answer(f"{pe('check')} +{len(new_lines)} строк. Итого: {total}.", parse_mode="HTML"); await state.clear()

@router.callback_query(F.data == "admin_edit_desc")
async def edit_desc(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        cats = await get_categories(s)
        t = "Категории:\n" + "\n".join(f"{c.id}: {c.name}" for c in cats) + "\n\nID категории:"
    await callback.message.edit_text(t); await state.set_state(EditDesc.category_id); await callback.answer()

@router.message(EditDesc.category_id)
async def ed_cat(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: cid = int(message.text)
    except Exception: await message.answer("Число."); return
    async with AsyncSessionLocal() as s:
        prods = await get_products_by_category(s, cid)
        t = "Товары:\n" + "\n".join(f"{p.id}: {p.name} | {(p.description or '—')[:40]}" for p in prods) + "\n\nID товара:"
    await state.update_data(category_id=cid); await message.answer(t); await state.set_state(EditDesc.product_id)

@router.message(EditDesc.product_id)
async def ed_prod(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: pid = int(message.text)
    except Exception: await message.answer("Число."); return
    await state.update_data(product_id=pid); await message.answer("Новое описание:"); await state.set_state(EditDesc.new_desc)

@router.message(EditDesc.new_desc)
async def ed_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    async with AsyncSessionLocal() as s:
        prod = await s.get(Product, data['product_id'])
        if not prod: await message.answer("Не найдено."); await state.clear(); return
        prod.description = message.text; await s.commit()
    await message.answer(f"{pe('check')} Описание обновлено.", parse_mode="HTML"); await state.clear()

@router.callback_query(F.data == "admin_edit_price")
async def edit_price(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        cats = await get_categories(s)
        t = "Категории:\n" + "\n".join(f"{c.id}: {c.name}" for c in cats) + "\n\nID категории:"
    await callback.message.edit_text(t); await state.set_state(EditPrice.category_id); await callback.answer()

@router.message(EditPrice.category_id)
async def ep_cat(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: cid = int(message.text)
    except Exception: await message.answer("Число."); return
    async with AsyncSessionLocal() as s:
        prods = await get_products_by_category(s, cid)
        t = "Товары:\n" + "\n".join(f"{p.id}: {p.name} — {p.price}$" for p in prods) + "\n\nID товара:"
    await state.update_data(category_id=cid); await message.answer(t); await state.set_state(EditPrice.product_id)

@router.message(EditPrice.product_id)
async def ep_prod(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: pid = int(message.text)
    except Exception: await message.answer("Число."); return
    await state.update_data(product_id=pid); await message.answer("Новая цена ($):"); await state.set_state(EditPrice.new_price)

@router.message(EditPrice.new_price)
async def ep_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: price = float(message.text.replace(',','.'))
    except Exception: await message.answer("Число."); return
    data = await state.get_data()
    async with AsyncSessionLocal() as s:
        prod = await s.get(Product, data['product_id'])
        if not prod: await message.answer("Не найдено."); await state.clear(); return
        prod.price = price; await s.commit()
    await message.answer(f"{pe('check')} Цена: {price}$", parse_mode="HTML"); await state.clear()

@router.callback_query(F.data == "admin_bulk_price")
async def bulk_price(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text(
        f"{pe('chart')} <b>Массовое изменение цен</b>\n\n"
        "• <code>+10%</code> — поднять на 10%\n"
        "• <code>-15%</code> — снизить на 15%\n"
        "• <code>=5</code> — установить 5$ всем",
        parse_mode="HTML", reply_markup=back_kb()
    )
    await state.set_state(BulkPrice.action); await callback.answer()

@router.message(BulkPrice.action)
async def bulk_price_exec(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    inp = message.text.strip()
    async with AsyncSessionLocal() as s:
        prods = (await s.execute(select(Product))).scalars().all()
        count = 0
        try:
            for p in prods:
                if inp.startswith('+') and inp.endswith('%'):
                    p.price = round(p.price * (1 + float(inp[1:-1])/100), 2)
                elif inp.startswith('-') and inp.endswith('%'):
                    p.price = round(p.price * (1 - float(inp[1:-1])/100), 2)
                elif inp.startswith('='):
                    p.price = float(inp[1:])
                else:
                    await message.answer("Формат: +10% или =5"); await state.clear(); return
                count += 1
        except Exception:
            await message.answer("Неверный формат."); await state.clear(); return
        await s.commit()
    await message.answer(f"{pe('check')} Обновлено {count} товаров.", parse_mode="HTML"); await state.clear()

@router.callback_query(F.data == "admin_refill_product")
async def refill_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        cats = await get_categories(s)
        t = "Категории:\n" + "\n".join(f"{c.id}: {c.name}" for c in cats) + "\n\nID категории:"
    await callback.message.edit_text(t); await state.set_state(RefillProduct.category_id); await callback.answer()

@router.message(RefillProduct.category_id)
async def rf_cat(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: cid = int(message.text)
    except Exception: await message.answer("Число."); return
    async with AsyncSessionLocal() as s:
        prods = await get_products_by_category(s, cid)
        t = "Товары:\n" + "\n".join(f"{p.id}: {p.name} ({p.quantity} шт.)" for p in prods) + "\n\nID товара:"
    await state.update_data(category_id=cid); await message.answer(t); await state.set_state(RefillProduct.product_id)

@router.message(RefillProduct.product_id)
async def rf_prod(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: pid = int(message.text)
    except Exception: await message.answer("Число."); return
    await state.update_data(product_id=pid); await message.answer("Введи строки:"); await state.set_state(RefillProduct.content)

@router.message(RefillProduct.content)
async def rf_content(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    new_lines = [l.strip() for l in message.text.split('\n') if l.strip()]
    async with AsyncSessionLocal() as s:
        prod = await s.get(Product, data['product_id'])
        existing = [l for l in (prod.content or "").split('\n') if l.strip()]
        prod.content = '\n'.join(existing + new_lines)
        prod.quantity = len([l for l in prod.content.split('\n') if l.strip()])
        prod.is_available = True
        total = prod.quantity
        notifies = (await s.execute(select(StockNotify).where(StockNotify.product_id == prod.id))).scalars().all()
        for n in notifies:
            try: await message.bot.send_message(n.user_id, f"{pe('bell')} Товар <b>{prod.name}</b> снова в наличии!", parse_mode="HTML")
            except Exception: pass
            await s.delete(n)
        await s.commit()
    await message.answer(f"{pe('check')} +{len(new_lines)} строк. Итого: {total}.", parse_mode="HTML"); await state.clear()

@router.callback_query(F.data == "admin_delete_lines")
async def del_lines(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        cats = await get_categories(s)
        t = "Категории:\n" + "\n".join(f"{c.id}: {c.name}" for c in cats) + "\n\nID категории:"
    await callback.message.edit_text(t); await state.set_state(DeleteLines.category_id); await callback.answer()

@router.message(DeleteLines.category_id)
async def dl_cat(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: cid = int(message.text)
    except Exception: await message.answer("Число."); return
    async with AsyncSessionLocal() as s:
        prods = await get_products_by_category(s, cid)
        t = "Товары:\n" + "\n".join(f"{p.id}: {p.name} ({p.quantity} шт.)" for p in prods) + "\n\nID товара:"
    await state.update_data(category_id=cid); await message.answer(t); await state.set_state(DeleteLines.product_id)

@router.message(DeleteLines.product_id)
async def dl_prod(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: pid = int(message.text)
    except Exception: await message.answer("Число."); return
    async with AsyncSessionLocal() as s:
        prod = await s.get(Product, pid)
        if not prod or not prod.content: await message.answer("Нет контента."); return
        lines = [l for l in prod.content.split('\n') if l.strip()]
        preview = "\n".join(f"{i+1}: {l}" for i, l in enumerate(lines[:15]))
        if len(lines) > 15: preview += f"\n...ещё {len(lines)-15}"
    await state.update_data(product_id=pid)
    await message.answer(f"Строк: {len(lines)}\n\n<code>{preview}</code>\n\nНомера через запятую или «всё кроме 1,2,3»", parse_mode="HTML")
    await state.set_state(DeleteLines.lines)

@router.message(DeleteLines.lines)
async def dl_exec(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data(); inp = message.text.strip()
    async with AsyncSessionLocal() as s:
        prod = await s.get(Product, data['product_id'])
        lines = [l for l in prod.content.split('\n') if l.strip()]
        if inp.lower().startswith("всё кроме"):
            try: keep = {int(n.strip()) for n in inp.lower().replace("всё кроме","").strip().split(',')}
            except Exception: await message.answer("Неверный формат."); return
            new_lines = [l for i,l in enumerate(lines,1) if i in keep]
        else:
            try: remove = {int(n.strip()) for n in inp.split(',')}
            except Exception: await message.answer("Числа через запятую."); return
            new_lines = [l for i,l in enumerate(lines,1) if i not in remove]
        prod.content = '\n'.join(new_lines) or None; prod.quantity = len(new_lines); await s.commit()
    await message.answer(f"{pe('check')} Осталось: {len(new_lines)} строк.", parse_mode="HTML"); await state.clear()

@router.callback_query(F.data == "admin_add_category")
async def add_cat(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text("Название:"); await state.set_state(AddCategory.name); await callback.answer()

@router.message(AddCategory.name)
async def ac_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(name=message.text); await message.answer("ID родителя (0=корневая):"); await state.set_state(AddCategory.parent_id)

@router.message(AddCategory.parent_id)
async def ac_parent(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: pid = int(message.text)
    except Exception: await message.answer("Число."); return
    data = await state.get_data()
    async with AsyncSessionLocal() as s:
        s.add(Category(name=data['name'], parent_id=pid if pid!=0 else None)); await s.commit()
    await message.answer(f"{pe('check')} «{data['name']}» создана.", parse_mode="HTML"); await state.clear()

@router.callback_query(F.data == "admin_delete_product")
async def del_prod(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        cats = await get_categories(s)
        t = "Категории:\n" + "\n".join(f"{c.id}: {c.name}" for c in cats) + "\n\nID категории:"
    await callback.message.edit_text(t); await state.set_state(DelProduct.category_id); await callback.answer()

@router.message(DelProduct.category_id)
async def dp_cat(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: cid = int(message.text)
    except Exception: await message.answer("Число."); return
    async with AsyncSessionLocal() as s:
        prods = await get_products_by_category(s, cid)
        t = "Товары:\n" + "\n".join(f"{p.id}: {p.name}" for p in prods) + "\n\nID товара:"
    await state.update_data(category_id=cid); await message.answer(t); await state.set_state(DelProduct.product_id)

@router.message(DelProduct.product_id)
async def dp_exec(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: pid = int(message.text)
    except Exception: await message.answer("Число."); return
    async with AsyncSessionLocal() as s:
        prod = await s.get(Product, pid)
        if not prod: await message.answer("Не найдено."); return
        name = prod.name; await s.delete(prod); await s.commit()
    await message.answer(f"{pe('check')} «{name}» удалён.", parse_mode="HTML"); await state.clear()

@router.callback_query(F.data == "admin_delete_category")
async def del_cat(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        cats = await get_categories(s)
        t = "Категории:\n" + "\n".join(f"{c.id}: {c.name}" for c in cats) + "\n\nID для удаления:"
    await callback.message.edit_text(t); await state.set_state(DelCategory.category_id); await callback.answer()

@router.message(DelCategory.category_id)
async def dc_exec(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: cid = int(message.text)
    except Exception: await message.answer("Число."); return
    async with AsyncSessionLocal() as s:
        cat = await s.get(Category, cid)
        if not cat: await message.answer("Нет такой категории."); return
        name = cat.name; await s.delete(cat); await s.commit()
    await message.answer(f"{pe('check')} «{name}» удалена.", parse_mode="HTML"); await state.clear()

@router.callback_query(F.data == "admin_promocodes")
async def promos_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text(f"{pe('gift')} <b>Промокоды</b>", parse_mode="HTML", reply_markup=admin_promos_kb())
    await callback.answer()

@router.callback_query(F.data == "promo_list")
async def promo_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        promos = (await s.execute(select(Promocode))).scalars().all()
    if not promos: await callback.answer("Пусто.", show_alert=True); return
    lines = [f"{pe('gift')} <b>Промокоды:</b>\n"]
    for p in promos:
        exp = p.expires_at.strftime('%d.%m.%Y') if p.expires_at else "∞"
        lines.append(f"{'✅' if p.is_active else '❌'} <code>{p.code}</code> +{p.bonus_amount}$ {p.used_count}/{p.max_activations or '∞'} до {exp}")
    await callback.message.answer("\n".join(lines), parse_mode="HTML", reply_markup=back_kb("admin_promocodes"))
    await callback.answer()

@router.callback_query(F.data == "promo_add")
async def promo_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text("Код промокода:"); await state.set_state(PromoAdd.code); await callback.answer()

@router.message(PromoAdd.code)
async def pa_code(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(code=message.text.strip()); await message.answer("Бонус ($):"); await state.set_state(PromoAdd.amount)

@router.message(PromoAdd.amount)
async def pa_amt(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: amt = float(message.text.replace(',','.'))
    except Exception: await message.answer("Число."); return
    await state.update_data(amount=amt); await message.answer("Макс. активаций (0=∞):"); await state.set_state(PromoAdd.max_activations)

@router.message(PromoAdd.max_activations)
async def pa_max(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: mx = int(message.text)
    except Exception: await message.answer("Число."); return
    await state.update_data(max_activations=None if mx==0 else mx); await message.answer("Срок дней (0=∞):"); await state.set_state(PromoAdd.expires_days)

@router.message(PromoAdd.expires_days)
async def pa_exp(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: days = int(message.text)
    except Exception: await message.answer("Число."); return
    data = await state.get_data()
    expires = datetime.utcnow() + timedelta(days=days) if days > 0 else None
    async with AsyncSessionLocal() as s:
        s.add(Promocode(code=data['code'], bonus_amount=data['amount'], max_activations=data.get('max_activations'), expires_at=expires))
        await s.commit()
    await message.answer(f"{pe('check')} «{data['code']}» создан.", parse_mode="HTML"); await state.clear()

@router.callback_query(F.data == "promo_delete")
async def promo_del(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text("Код для удаления:"); await state.set_state(PromoDel.code); await callback.answer()

@router.message(PromoDel.code)
async def pd_exec(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    async with AsyncSessionLocal() as s:
        p = await s.get(Promocode, message.text.strip())
        if not p: await message.answer("Не найден."); await state.clear(); return
        await s.delete(p); await s.commit()
    await message.answer(f"{pe('check')} Удалён.", parse_mode="HTML"); await state.clear()

@router.callback_query(F.data == "admin_users_menu")
async def users_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text(f"{pe('users')} <b>Пользователи</b>", parse_mode="HTML", reply_markup=admin_users_kb())
    await callback.answer()

@router.callback_query(F.data == "user_search")
async def user_search(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text(f"{pe('search')} ID:", parse_mode="HTML")
    await state.set_state(UserFind.user_id); await callback.answer()

@router.message(UserFind.user_id)
async def us_show(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: uid = int(message.text.strip())
    except Exception: await message.answer("Число."); return
    async with AsyncSessionLocal() as s:
        user = await s.get(User, uid)
        if not user: await message.answer("Не найден."); await state.clear(); return
        buys = len((await s.execute(select(Purchase).where(Purchase.user_id == uid))).scalars().all())
        await message.answer(
            f"{pe('user')} <code>{uid}</code> @{user.username or '—'}\n"
            f"{pe('wallet')} {user.balance:.2f}$  |  потрачено: {user.total_spent:.2f}$\n"
            f"{pe('briefcase')} Покупок: {buys}\n"
            f"{pe('star2')} Кэшбек: {user.cashback_pct}%  |  рефералов: {user.ref_count}\n"
            f"{'🚫 Бан: '+(user.ban_reason or '—') if user.is_banned else '✅ Активен'}\n"
            f"{pe('clock')} {user.registered_at.strftime('%d.%m.%Y')}",
            parse_mode="HTML"
        )
    await state.clear()

@router.callback_query(F.data == "user_balance")
async def user_bal(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text(f"{pe('wallet')} ID:", parse_mode="HTML")
    await state.set_state(UserBal.user_id); await callback.answer()

@router.message(UserBal.user_id)
async def ub_uid(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: uid = int(message.text)
    except Exception: await message.answer("Число."); return
    async with AsyncSessionLocal() as s:
        user = await s.get(User, uid)
        if not user: await message.answer("Не найден."); await state.clear(); return
    await state.update_data(user_id=uid); await message.answer(f"Баланс: {user.balance:.2f}$\n+10, -5 или =100:"); await state.set_state(UserBal.amount)

@router.message(UserBal.amount)
async def ub_set(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data(); txt = message.text.strip()
    async with AsyncSessionLocal() as s:
        user = await s.get(User, data['user_id'])
        try:
            if txt.startswith('+'): user.balance += float(txt[1:])
            elif txt.startswith('-'): user.balance -= float(txt[1:])
            else: user.balance = float(txt)
        except Exception: await message.answer("Неверный формат."); return
        await s.commit()
        await message.answer(f"{pe('check')} Баланс: {user.balance:.2f}$", parse_mode="HTML")
    await state.clear()

@router.callback_query(F.data == "user_ban")
async def user_ban(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text(f"{pe('ban')} ID:", parse_mode="HTML")
    await state.set_state(UserBan.user_id); await callback.answer()

@router.message(UserBan.user_id)
async def ban_uid(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: uid = int(message.text)
    except Exception: await message.answer("Число."); return
    async with AsyncSessionLocal() as s:
        user = await s.get(User, uid)
        if not user: await message.answer("Не найден."); await state.clear(); return
        if user.is_banned:
            user.is_banned = False; user.ban_reason = None; await s.commit()
            await message.answer(f"{pe('check')} {uid} разбанен.", parse_mode="HTML"); await state.clear(); return
    await state.update_data(user_id=uid); await message.answer("Причина:"); await state.set_state(UserBan.reason)

@router.message(UserBan.reason)
async def ban_exec(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    async with AsyncSessionLocal() as s:
        user = await s.get(User, data['user_id']); user.is_banned = True; user.ban_reason = message.text; await s.commit()
    try:
        await message.bot.send_message(data['user_id'], f"{pe('ban')} Вы заблокированы.\nПричина: {message.text}", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Разжаловать", callback_data="unban_request")]]))
    except Exception: pass
    await message.answer(f"{pe('check')} {data['user_id']} заблокирован.", parse_mode="HTML"); await state.clear()

@router.callback_query(F.data == "user_cashback")
async def user_cb_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.edit_text(f"{pe('star')} ID пользователя:", parse_mode="HTML")
    await state.set_state(UserCashback.user_id); await callback.answer()

@router.message(UserCashback.user_id)
async def ucb_uid(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: uid = int(message.text)
    except Exception: await message.answer("Число."); return
    await state.update_data(user_id=uid); await message.answer("Новый % кэшбека:"); await state.set_state(UserCashback.pct)

@router.message(UserCashback.pct)
async def ucb_set(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: pct = float(message.text.replace(',','.'))
    except Exception: await message.answer("Число."); return
    data = await state.get_data()
    async with AsyncSessionLocal() as s:
        user = await s.get(User, data['user_id'])
        if not user: await message.answer("Не найден."); await state.clear(); return
        user.cashback_pct = pct; await s.commit()
    await message.answer(f"{pe('check')} Кэшбек: {pct}%", parse_mode="HTML"); await state.clear()

@router.callback_query(F.data == "admin_replaces")
async def admin_replaces(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        reqs = (await s.execute(select(ReplaceRequest).where(ReplaceRequest.status=='pending').limit(20))).scalars().all()
    if not reqs: await callback.answer("Заявок нет.", show_alert=True); return
    lines = [f"{pe('hammer')} <b>Замены:</b>\n"]
    for r in reqs:
        lines.append(f"#{r.id} | {r.user_id} | {r.created_at.strftime('%d.%m %H:%M')}")
    await callback.message.answer("\n".join(lines), parse_mode="HTML", reply_markup=back_kb()); await callback.answer()

@router.callback_query(F.data.startswith("replace_approve_"))
async def repl_approve(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await state.update_data(req_id=int(callback.data.split("_")[2]))
    await callback.message.answer("Сообщение (одобрение):"); await state.set_state(ReplaceApprove.message); await callback.answer()

@router.message(ReplaceApprove.message)
async def repl_approve_msg(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    async with AsyncSessionLocal() as s:
        req = await s.get(ReplaceRequest, data['req_id'])
        if req:
            req.status = 'approved'; req.admin_comment = message.text; await s.commit()
            try: await message.bot.send_message(req.user_id, f"{pe('check')} Замена #{req.id} одобрена.\n{message.text}", parse_mode="HTML")
            except Exception: pass
    await message.answer(f"{pe('check')} Одобрено.", parse_mode="HTML"); await state.clear()

@router.callback_query(F.data.startswith("replace_reject_"))
async def repl_reject(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await state.update_data(req_id=int(callback.data.split("_")[2]))
    await callback.message.answer("Причина:"); await state.set_state(ReplaceReject.reason); await callback.answer()

@router.message(ReplaceReject.reason)
async def repl_reject_msg(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    async with AsyncSessionLocal() as s:
        req = await s.get(ReplaceRequest, data['req_id'])
        if req:
            req.status = 'rejected'; req.admin_comment = message.text; await s.commit()
            try: await message.bot.send_message(req.user_id, f"{pe('ban')} Замена #{req.id} отклонена.\n{message.text}", parse_mode="HTML")
            except Exception: pass
    await message.answer(f"{pe('check')} Отклонено.", parse_mode="HTML"); await state.clear()

@router.callback_query(F.data.startswith("unban_approve_"))
async def unban_approve(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        req = await s.get(UnbanRequest, int(callback.data.split("_")[2]))
        if req:
            req.status = 'approved'
            user = await s.get(User, req.user_id)
            if user: user.is_banned = False; user.ban_reason = None
            await s.commit()
            try: await callback.bot.send_message(req.user_id, f"{pe('unlock')} Вы разблокированы.", parse_mode="HTML")
            except Exception: pass
    await callback.message.answer(f"{pe('check')} Разблокирован.", parse_mode="HTML"); await callback.answer()

@router.callback_query(F.data.startswith("unban_reject_"))
async def unban_reject(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        req = await s.get(UnbanRequest, int(callback.data.split("_")[2]))
        if req:
            req.status = 'rejected'; await s.commit()
            try: await callback.bot.send_message(req.user_id, f"{pe('ban')} В разблокировке отказано.", parse_mode="HTML")
            except Exception: pass
    await callback.message.answer(f"{pe('check')} Отклонено.", parse_mode="HTML"); await callback.answer()
