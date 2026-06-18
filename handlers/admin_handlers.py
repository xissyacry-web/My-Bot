from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
from sqlalchemy import select, func, text
import os, sqlite3, shutil, sys

from database.database import AsyncSessionLocal
from database.models import (
    User, Product, Category, Promocode, UnbanRequest, Invoice,
    Purchase, ReplaceRequest, ScheduledBroadcast, StockNotify
)
from config import ADMIN_IDS, VERSION, pe
from utils.states import *
from services.product_service import get_categories, get_products_by_category
from keyboards.kb import (
    admin_main, admin_back, admin_promos, admin_users,
    broadcast_timing, ibtn, to_main, replace_action, unban_action,
)

router = Router()

def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS

def back_kb(cb="admin_back"):
    from aiogram.types import InlineKeyboardMarkup
    return InlineKeyboardMarkup(inline_keyboard=[[ibtn("Назад", cb, emoji_key="home", style="primary")]])

async def safe_edit(target, text_: str, kb=None):
    """Безопасный edit_text с fallback на answer"""
    try:
        await target.edit_text(text_, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await target.answer(text_, parse_mode="HTML", reply_markup=kb)

# ── "УМНЫЙ" ПЕРЕХВАТ ──────────────────────────────────────────────────────────
# Список текстов, которые ВСЕГДА должны прерывать любое FSM-состояние админа
ADMIN_INTERRUPT_TRIGGERS = {
    "/admin", "/panel", "Панель", "/start",
    "Каталог", "Профиль", "Замена", "Поддержка", "Скидка",
}

async def is_interrupt(message: Message) -> bool:
    """Если пользователь прислал новую команду/кнопку — сбрасываем старое состояние"""
    return message.text in ADMIN_INTERRUPT_TRIGGERS or (message.text or "").startswith("/")

# ── ГЛАВНОЕ МЕНЮ АДМИНА ───────────────────────────────────────────────────────
@router.message(F.text.in_({"/admin", "/panel", "Панель"}))
async def admin_panel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer(
        f"{pe('crown')} <b>Панель управления {VERSION}</b>",
        parse_mode="HTML", reply_markup=admin_main()
    )

@router.callback_query(F.data == "admin_back")
async def adm_back(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(); return
    await state.clear()
    await safe_edit(callback.message, f"{pe('crown')} <b>Панель управления {VERSION}</b>", admin_main())
    await callback.answer()

@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()

# ── ЭКСПОРТ / ИМПОРТ БД ───────────────────────────────────────────────────────
@router.callback_query(F.data == "admin_export")
async def export_db(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    token = os.environ.get("IMPORT_TOKEN", "secret123")
    url = os.environ.get("RENDER_EXTERNAL_URL", "https://your-bot.onrender.com")
    async with AsyncSessionLocal() as s:
        try:
            await s.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
            await s.commit()
        except Exception:
            pass
    try:
        await callback.message.answer_document(
            FSInputFile("bot.db"),
            caption=f"{pe('download')} <b>Экспорт БД</b>\n\nИли по ссылке:\n<code>{url}/export?token={token}</code>",
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            f"{pe('download')} Скачай БД по ссылке:\n<code>{url}/export?token={token}</code>",
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data == "admin_import")
async def import_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    token = os.environ.get("IMPORT_TOKEN", "secret123")
    url = os.environ.get("RENDER_EXTERNAL_URL", "https://your-bot.onrender.com")
    await safe_edit(
        callback.message,
        f"{pe('warning')} <b>Импорт БД</b>\n\n"
        f"Отправь файл <code>bot.db</code> сюда, или через браузер:\n"
        f"<code>POST {url}/import?token={token}</code>",
        back_kb()
    )
    await state.set_state(ImportDB.file)
    await callback.answer()

@router.message(ImportDB.file, F.document)
async def import_file(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if not message.document.file_name.endswith(".db"):
        await message.answer(f"{pe('warning')} Нужен файл .db", parse_mode="HTML"); return
    file = await message.bot.get_file(message.document.file_id)
    temp = "bot.db.tmp"
    await message.bot.download_file(file.file_path, temp)
    try:
        conn = sqlite3.connect(temp)
        conn.execute("SELECT 1 FROM users LIMIT 1")
        conn.close()
    except Exception:
        await message.answer(f"{pe('ban')} Неверный файл БД.", parse_mode="HTML")
        os.remove(temp)
        return
    if os.path.exists("bot.db"):
        shutil.copy2("bot.db", "backup.db")
    os.replace(temp, "bot.db")
    await message.answer(f"{pe('check')} Импортировано! Перезапуск...", parse_mode="HTML")
    await state.clear()
    sys.exit(0)

@router.message(ImportDB.file)
async def import_file_wrong(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear()
        return  # пусть перехватят другие хендлеры
    await message.answer(f"{pe('warning')} Отправь файл .db (документом).", parse_mode="HTML")

# ── СТАТИСТИКА ────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "admin_stats")
async def stats_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    b = InlineKeyboardBuilder()
    b.add(ibtn("День", "stats_day"))
    b.add(ibtn("7 дней", "stats_week"))
    b.add(ibtn("30 дней", "stats_month"))
    b.add(ibtn("Назад", "admin_back", emoji_key="home", style="primary"))
    b.adjust(3, 1)
    await safe_edit(callback.message, f"{pe('chart')} Выбери период:", b.as_markup())
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
        topc  = (await s.execute(select(func.count(Invoice.id)).where(Invoice.created_at >= since, Invoice.status=='paid'))).scalar()
        tops  = (await s.execute(select(func.sum(Invoice.amount)).where(Invoice.created_at >= since, Invoice.status=='paid'))).scalar() or 0
        total = (await s.execute(select(func.count(User.user_id)))).scalar()
    await safe_edit(callback.message,
        f"{pe('chart')} <b>Статистика за {days} дн.</b>\n\n"
        f"{pe('users')} Новых: {new_u}  |  всего {total}\n"
        f"{pe('cart')} Покупок: {buys}  ({rev:.2f}$)\n"
        f"{pe('wallet')} Пополнений: {topc}  ({tops:.2f}$)",
        back_kb("admin_stats")
    )
    await callback.answer()

@router.callback_query(F.data == "a_top")
async def top_buyers(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(User.user_id, User.username, User.total_spent)
            .order_by(User.total_spent.desc()).limit(10)
        )).all()
    if not rows:
        await callback.answer("Пусто.", show_alert=True); return
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    lines = [f"{pe('crown')} <b>Топ покупателей</b>\n"]
    for i, (uid, uname, spent) in enumerate(rows):
        name = f"@{uname}" if uname else f"id:{uid}"
        lines.append(f"{medals[i]} {name} — {spent:.2f}$")
    await callback.message.answer("\n".join(lines), parse_mode="HTML", reply_markup=back_kb())
    await callback.answer()

@router.callback_query(F.data == "admin_view_logs")
async def view_logs_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await safe_edit(callback.message, f"{pe('books')} Введи ID пользователя:", back_kb())
    await state.set_state(ViewLogs.user_id)
    await callback.answer()

@router.message(ViewLogs.user_id)
async def view_logs_show(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        uid = int(message.text.strip())
    except Exception:
        await message.answer(f"{pe('warning')} Нужно число (ID пользователя).", parse_mode="HTML"); return
    async with AsyncSessionLocal() as s:
        purchases = (await s.execute(
            select(Purchase).where(Purchase.user_id == uid)
            .order_by(Purchase.purchased_at.desc()).limit(20)
        )).scalars().all()
        if not purchases:
            await message.answer(f"{pe('warning')} У пользователя {uid} нет покупок.", parse_mode="HTML")
            await state.clear(); return
        lines = [f"{pe('books')} <b>Покупки {uid}:</b>\n"]
        for p in purchases:
            prod = await s.get(Product, p.product_id)
            pname = prod.name if prod else "удалён"
            lines.append(f"#{p.id} <b>{pname}</b> ×{p.amount} — {p.price:.2f}$ — {p.purchased_at.strftime('%d.%m %H:%M')}")
    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=back_kb())
    await state.clear()

# ── РАССЫЛКА ──────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await safe_edit(callback.message, f"{pe('mega')} Введи текст рассылки (HTML поддерживается):", back_kb())
    await state.set_state(Broadcast.text)
    await callback.answer()

@router.message(Broadcast.text)
async def broadcast_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    await state.update_data(text=message.text)
    await message.answer("Когда отправить?", reply_markup=broadcast_timing())
    await state.set_state(Broadcast.schedule)

@router.callback_query(Broadcast.schedule, F.data == "bc_now")
async def broadcast_now(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    data = await state.get_data()
    await state.clear()
    async with AsyncSessionLocal() as s:
        users = (await s.execute(select(User.user_id))).scalars().all()
    ok = fail = 0
    for uid in users:
        try:
            await callback.bot.send_message(uid, data["text"], parse_mode="HTML")
            ok += 1
        except Exception:
            fail += 1
    from services.log_service import log_broadcast
    await log_broadcast(callback.bot, callback.from_user.id, data["text"], ok, fail)
    await callback.message.answer(f"{pe('check')} Доставлено: {ok}, ошибок: {fail}.", parse_mode="HTML", reply_markup=back_kb())
    await callback.answer()

@router.callback_query(Broadcast.schedule, F.data == "bc_schedule")
async def broadcast_schedule_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await callback.message.answer(f"{pe('clock')} Дата и время в формате <b>ДД.ММ.ГГГГ ЧЧ:ММ</b>:", parse_mode="HTML")
    await callback.answer()

@router.message(Broadcast.schedule)
async def broadcast_schedule_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        send_at = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
    except Exception:
        await message.answer(f"{pe('warning')} Неверный формат. Пример: 25.12.2026 18:00", parse_mode="HTML")
        return
    data = await state.get_data()
    async with AsyncSessionLocal() as s:
        s.add(ScheduledBroadcast(text=data["text"], send_at=send_at))
        await s.commit()
    await message.answer(f"{pe('check')} Запланировано на {send_at.strftime('%d.%m.%Y %H:%M')}", parse_mode="HTML", reply_markup=back_kb())
    await state.clear()

@router.callback_query(F.data == "admin_scheduled")
async def admin_scheduled(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        items = (await s.execute(select(ScheduledBroadcast).where(ScheduledBroadcast.sent == False))).scalars().all()
    if not items:
        await callback.answer("Нет запланированных.", show_alert=True); return
    lines = [f"{pe('clock')} <b>Запланированные рассылки:</b>\n"]
    for i in items:
        lines.append(f"#{i.id} · {i.send_at.strftime('%d.%m.%Y %H:%M')}\n<i>{i.text[:60]}</i>")
    await callback.message.answer("\n\n".join(lines), parse_mode="HTML", reply_markup=back_kb())
    await callback.answer()

# ── ДОБАВИТЬ ТОВАР ────────────────────────────────────────────────────────────
@router.callback_query(F.data == "a_add_prod")
async def add_prod(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        cats = await get_categories(s)
        if not cats:
            await safe_edit(callback.message, f"{pe('warning')} Сначала создай категорию.", back_kb())
            await callback.answer(); return
        listing = "\n".join(f"{c.id}: {c.name}" for c in cats)
    await safe_edit(callback.message, f"{pe('folder')} <b>Категории:</b>\n{listing}\n\nВведи ID категории:", back_kb())
    await state.set_state(AddProduct.category_id)
    await callback.answer()

@router.message(AddProduct.category_id)
async def ap_cat(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        cid = int(message.text.strip())
    except Exception:
        await message.answer(f"{pe('warning')} Нужно число (ID категории).", parse_mode="HTML"); return
    async with AsyncSessionLocal() as s:
        if not await s.get(Category, cid):
            await message.answer(f"{pe('ban')} Категория с ID {cid} не найдена.", parse_mode="HTML"); return
    await state.update_data(category_id=cid)
    await message.answer(f"{pe('palette')} Название товара:", parse_mode="HTML")
    await state.set_state(AddProduct.name)

@router.message(AddProduct.name)
async def ap_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    await state.update_data(name=message.text)
    await message.answer("Описание (или «-» чтобы пропустить):")
    await state.set_state(AddProduct.description)

@router.message(AddProduct.description)
async def ap_desc(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    await state.update_data(description=None if message.text.strip() == "-" else message.text)
    await message.answer(f"{pe('wallet')} Цена в $:", parse_mode="HTML")
    await state.set_state(AddProduct.price)

@router.message(AddProduct.price)
async def ap_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        p = float(message.text.replace(",", ".").strip())
        if p < 0: raise ValueError
    except Exception:
        await message.answer(f"{pe('warning')} Нужно число, например 2.5", parse_mode="HTML"); return
    await state.update_data(price=p)
    await message.answer("Количество (0 = неограничено):")
    await state.set_state(AddProduct.quantity)

@router.message(AddProduct.quantity)
async def ap_qty(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        q = int(message.text.strip())
        if q < 0: raise ValueError
    except Exception:
        await message.answer(f"{pe('warning')} Нужно целое число.", parse_mode="HTML"); return
    await state.update_data(quantity=q)
    await message.answer("Контент товара построчно (или «-» если будешь добавлять позже):")
    await state.set_state(AddProduct.content)

@router.message(AddProduct.content)
async def ap_content(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    await state.update_data(content=None if message.text.strip() == "-" else message.text)
    await message.answer("Прикрепи файл (документ) или напиши «-» чтобы пропустить:")
    await state.set_state(AddProduct.file)

@router.message(AddProduct.file)
async def ap_file(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if message.text and await is_interrupt(message):
        await state.clear(); return
    data = await state.get_data()
    fid = message.document.file_id if message.document else None
    content = data.get("content")
    qty = data.get("quantity", 0)
    if content:
        lines = [l for l in content.split("\n") if l.strip()]
        qty = len(lines)
    async with AsyncSessionLocal() as s:
        prod = Product(
            category_id=data["category_id"], name=data["name"], description=data.get("description"),
            price=data["price"], quantity=qty, content=content, file_id=fid
        )
        s.add(prod)
        await s.commit()
    await message.answer(f"{pe('check')} Товар «{data['name']}» добавлен!", parse_mode="HTML", reply_markup=back_kb())
    await state.clear()

# ── ПОПОЛНИТЬ ТОВАР (добавить строк) ──────────────────────────────────────────
@router.callback_query(F.data == "a_refill")
async def refill_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        cats = await get_categories(s)
        if not cats:
            await safe_edit(callback.message, f"{pe('warning')} Нет категорий.", back_kb()); await callback.answer(); return
        listing = "\n".join(f"{c.id}: {c.name}" for c in cats)
    await safe_edit(callback.message, f"{pe('folder')} <b>Категории:</b>\n{listing}\n\nID категории:", back_kb())
    await state.set_state(RefillProduct.category_id)
    await callback.answer()

@router.message(RefillProduct.category_id)
async def rf_cat(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        cid = int(message.text.strip())
    except Exception:
        await message.answer(f"{pe('warning')} Нужно число.", parse_mode="HTML"); return
    async with AsyncSessionLocal() as s:
        prods = await get_products_by_category(s, cid)
        if not prods:
            await message.answer(f"{pe('warning')} Нет товаров в этой категории.", parse_mode="HTML"); return
        listing = "\n".join(f"{p.id}: {p.name} ({p.quantity} шт.)" for p in prods)
    await state.update_data(category_id=cid)
    await message.answer(f"{pe('box')} <b>Товары:</b>\n{listing}\n\nID товара:", parse_mode="HTML")
    await state.set_state(RefillProduct.product_id)

@router.message(RefillProduct.product_id)
async def rf_prod(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        pid = int(message.text.strip())
    except Exception:
        await message.answer(f"{pe('warning')} Нужно число.", parse_mode="HTML"); return
    async with AsyncSessionLocal() as s:
        if not await s.get(Product, pid):
            await message.answer(f"{pe('ban')} Товар не найден.", parse_mode="HTML"); return
    await state.update_data(product_id=pid)
    await message.answer("Введи строки товара (каждая с новой строки):")
    await state.set_state(RefillProduct.content)

@router.message(RefillProduct.content)
async def rf_content(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    data = await state.get_data()
    new_lines = [l.strip() for l in message.text.split("\n") if l.strip()]
    async with AsyncSessionLocal() as s:
        prod = await s.get(Product, data["product_id"])
        if not prod:
            await message.answer(f"{pe('ban')} Товар не найден.", parse_mode="HTML"); await state.clear(); return
        existing = [l for l in (prod.content or "").split("\n") if l.strip()]
        prod.content = "\n".join(existing + new_lines)
        prod.quantity = len(existing) + len(new_lines)
        prod.is_available = True
        total = prod.quantity
        notifies = (await s.execute(select(StockNotify).where(StockNotify.product_id == prod.id))).scalars().all()
        for n in notifies:
            try:
                await message.bot.send_message(n.user_id, f"{pe('bell')} Товар <b>{prod.name}</b> снова в наличии!", parse_mode="HTML")
            except Exception: pass
            await s.delete(n)
        await s.commit()
    await message.answer(f"{pe('check')} +{len(new_lines)} строк. Итого: {total}.", parse_mode="HTML", reply_markup=back_kb())
    await state.clear()

# ── ЗАГРУЗКА TXT ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "a_bulk_txt")
async def bulk_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        cats = await get_categories(s)
        if not cats:
            await safe_edit(callback.message, f"{pe('warning')} Нет категорий.", back_kb()); await callback.answer(); return
        listing = "\n".join(f"{c.id}: {c.name}" for c in cats)
    await safe_edit(callback.message, f"{pe('folder')} <b>Категории:</b>\n{listing}\n\nID категории:", back_kb())
    await state.set_state(BulkTxt.category_id)
    await callback.answer()

@router.message(BulkTxt.category_id)
async def bulk_cat(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        cid = int(message.text.strip())
    except Exception:
        await message.answer(f"{pe('warning')} Нужно число.", parse_mode="HTML"); return
    async with AsyncSessionLocal() as s:
        prods = await get_products_by_category(s, cid)
        if not prods:
            await message.answer(f"{pe('warning')} Нет товаров в категории.", parse_mode="HTML"); return
        listing = "\n".join(f"{p.id}: {p.name}" for p in prods)
    await state.update_data(category_id=cid)
    await message.answer(f"{pe('box')} <b>Товары:</b>\n{listing}\n\nID товара:", parse_mode="HTML")
    await state.set_state(BulkTxt.product_id)

@router.message(BulkTxt.product_id)
async def bulk_prod(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        pid = int(message.text.strip())
    except Exception:
        await message.answer(f"{pe('warning')} Нужно число.", parse_mode="HTML"); return
    async with AsyncSessionLocal() as s:
        if not await s.get(Product, pid):
            await message.answer(f"{pe('ban')} Товар не найден.", parse_mode="HTML"); return
    await state.update_data(product_id=pid)
    await message.answer(f"{pe('download')} Отправь .txt файл (каждая строка = единица товара):", parse_mode="HTML")
    await state.set_state(BulkTxt.file)

@router.message(BulkTxt.file, F.document)
async def bulk_file(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if not message.document.file_name.endswith(".txt"):
        await message.answer(f"{pe('warning')} Нужен файл .txt", parse_mode="HTML"); return
    data = await state.get_data()
    f = await message.bot.get_file(message.document.file_id)
    raw = (await message.bot.download_file(f.file_path)).read().decode("utf-8", errors="replace")
    new_lines = [l.strip() for l in raw.split("\n") if l.strip()]
    if not new_lines:
        await message.answer(f"{pe('warning')} Файл пустой.", parse_mode="HTML"); await state.clear(); return
    async with AsyncSessionLocal() as s:
        prod = await s.get(Product, data["product_id"])
        if not prod:
            await message.answer(f"{pe('ban')} Товар не найден.", parse_mode="HTML"); await state.clear(); return
        existing = [l for l in (prod.content or "").split("\n") if l.strip()]
        prod.content = "\n".join(existing + new_lines)
        prod.quantity = len(existing) + len(new_lines)
        prod.is_available = True
        total = prod.quantity
        notifies = (await s.execute(select(StockNotify).where(StockNotify.product_id == prod.id))).scalars().all()
        for n in notifies:
            try:
                await message.bot.send_message(n.user_id, f"{pe('bell')} Товар <b>{prod.name}</b> снова в наличии!", parse_mode="HTML")
            except Exception: pass
            await s.delete(n)
        await s.commit()
    await message.answer(f"{pe('check')} +{len(new_lines)} строк. Итого: {total}.", parse_mode="HTML", reply_markup=back_kb())
    await state.clear()

@router.message(BulkTxt.file)
async def bulk_file_wrong(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    await message.answer(f"{pe('warning')} Нужен документ .txt, а не текст.", parse_mode="HTML")

# ── ИЗМЕНИТЬ ОПИСАНИЕ ─────────────────────────────────────────────────────────
@router.callback_query(F.data == "a_edit_desc")
async def edit_desc(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        cats = await get_categories(s)
        if not cats:
            await safe_edit(callback.message, f"{pe('warning')} Нет категорий.", back_kb()); await callback.answer(); return
        listing = "\n".join(f"{c.id}: {c.name}" for c in cats)
    await safe_edit(callback.message, f"{pe('folder')} <b>Категории:</b>\n{listing}\n\nID категории:", back_kb())
    await state.set_state(EditDesc.category_id)
    await callback.answer()

@router.message(EditDesc.category_id)
async def ed_cat(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        cid = int(message.text.strip())
    except Exception:
        await message.answer(f"{pe('warning')} Нужно число.", parse_mode="HTML"); return
    async with AsyncSessionLocal() as s:
        prods = await get_products_by_category(s, cid)
        if not prods:
            await message.answer(f"{pe('warning')} Нет товаров.", parse_mode="HTML"); return
        listing = "\n".join(f"{p.id}: {p.name} | {(p.description or '—')[:40]}" for p in prods)
    await state.update_data(category_id=cid)
    await message.answer(f"{pe('box')} <b>Товары:</b>\n{listing}\n\nID товара:", parse_mode="HTML")
    await state.set_state(EditDesc.product_id)

@router.message(EditDesc.product_id)
async def ed_prod(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        pid = int(message.text.strip())
    except Exception:
        await message.answer(f"{pe('warning')} Нужно число.", parse_mode="HTML"); return
    async with AsyncSessionLocal() as s:
        if not await s.get(Product, pid):
            await message.answer(f"{pe('ban')} Товар не найден.", parse_mode="HTML"); return
    await state.update_data(product_id=pid)
    await message.answer("Новое описание:")
    await state.set_state(EditDesc.text)

@router.message(EditDesc.text)
async def ed_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    data = await state.get_data()
    async with AsyncSessionLocal() as s:
        prod = await s.get(Product, data["product_id"])
        if not prod:
            await message.answer(f"{pe('ban')} Не найдено.", parse_mode="HTML"); await state.clear(); return
        prod.description = message.text
        await s.commit()
    await message.answer(f"{pe('check')} Описание обновлено.", parse_mode="HTML", reply_markup=back_kb())
    await state.clear()

# ── ИЗМЕНИТЬ ЦЕНУ ─────────────────────────────────────────────────────────────
@router.callback_query(F.data == "a_edit_price")
async def edit_price(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        cats = await get_categories(s)
        if not cats:
            await safe_edit(callback.message, f"{pe('warning')} Нет категорий.", back_kb()); await callback.answer(); return
        listing = "\n".join(f"{c.id}: {c.name}" for c in cats)
    await safe_edit(callback.message, f"{pe('folder')} <b>Категории:</b>\n{listing}\n\nID категории:", back_kb())
    await state.set_state(EditPrice.category_id)
    await callback.answer()

@router.message(EditPrice.category_id)
async def ep_cat(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        cid = int(message.text.strip())
    except Exception:
        await message.answer(f"{pe('warning')} Нужно число.", parse_mode="HTML"); return
    async with AsyncSessionLocal() as s:
        prods = await get_products_by_category(s, cid)
        if not prods:
            await message.answer(f"{pe('warning')} Нет товаров.", parse_mode="HTML"); return
        listing = "\n".join(f"{p.id}: {p.name} — {p.price}$" for p in prods)
    await state.update_data(category_id=cid)
    await message.answer(f"{pe('box')} <b>Товары:</b>\n{listing}\n\nID товара:", parse_mode="HTML")
    await state.set_state(EditPrice.product_id)

@router.message(EditPrice.product_id)
async def ep_prod(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        pid = int(message.text.strip())
    except Exception:
        await message.answer(f"{pe('warning')} Нужно число.", parse_mode="HTML"); return
    async with AsyncSessionLocal() as s:
        if not await s.get(Product, pid):
            await message.answer(f"{pe('ban')} Товар не найден.", parse_mode="HTML"); return
    await state.update_data(product_id=pid)
    await message.answer(f"{pe('wallet')} Новая цена в $:", parse_mode="HTML")
    await state.set_state(EditPrice.price)

@router.message(EditPrice.price)
async def ep_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        price = float(message.text.replace(",", ".").strip())
        if price < 0: raise ValueError
    except Exception:
        await message.answer(f"{pe('warning')} Нужно число.", parse_mode="HTML"); return
    data = await state.get_data()
    async with AsyncSessionLocal() as s:
        prod = await s.get(Product, data["product_id"])
        if not prod:
            await message.answer(f"{pe('ban')} Не найдено.", parse_mode="HTML"); await state.clear(); return
        prod.price = price
        await s.commit()
    await message.answer(f"{pe('check')} Цена обновлена: {price}$", parse_mode="HTML", reply_markup=back_kb())
    await state.clear()

# ── МАССОВО ИЗМЕНИТЬ ЦЕНЫ ─────────────────────────────────────────────────────
@router.callback_query(F.data == "a_bulk_price")
async def bulk_price(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await safe_edit(callback.message,
        f"{pe('chart')} <b>Массовое изменение цен</b>\n\n"
        f"• <code>+10%</code> — поднять все цены на 10%\n"
        f"• <code>-15%</code> — снизить все цены на 15%\n"
        f"• <code>=5</code> — установить всем цену 5$",
        back_kb()
    )
    await state.set_state(BulkPrice.action)
    await callback.answer()

@router.message(BulkPrice.action)
async def bulk_price_exec(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    inp = message.text.strip()
    async with AsyncSessionLocal() as s:
        prods = (await s.execute(select(Product))).scalars().all()
        count = 0
        try:
            for p in prods:
                if inp.startswith("+") and inp.endswith("%"):
                    p.price = round(p.price * (1 + float(inp[1:-1]) / 100), 2)
                elif inp.startswith("-") and inp.endswith("%"):
                    p.price = round(p.price * (1 - float(inp[1:-1]) / 100), 2)
                elif inp.startswith("="):
                    p.price = float(inp[1:])
                else:
                    await message.answer(f"{pe('warning')} Формат: +10% / -15% / =5", parse_mode="HTML")
                    return
                count += 1
        except Exception:
            await message.answer(f"{pe('warning')} Неверный формат.", parse_mode="HTML"); return
        await s.commit()
    await message.answer(f"{pe('check')} Обновлено {count} товаров.", parse_mode="HTML", reply_markup=back_kb())
    await state.clear()

# ── УДАЛИТЬ СТРОКИ ────────────────────────────────────────────────────────────
@router.callback_query(F.data == "a_del_lines")
async def del_lines(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        cats = await get_categories(s)
        if not cats:
            await safe_edit(callback.message, f"{pe('warning')} Нет категорий.", back_kb()); await callback.answer(); return
        listing = "\n".join(f"{c.id}: {c.name}" for c in cats)
    await safe_edit(callback.message, f"{pe('folder')} <b>Категории:</b>\n{listing}\n\nID категории:", back_kb())
    await state.set_state(DeleteLines.category_id)
    await callback.answer()

@router.message(DeleteLines.category_id)
async def dl_cat(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        cid = int(message.text.strip())
    except Exception:
        await message.answer(f"{pe('warning')} Нужно число.", parse_mode="HTML"); return
    async with AsyncSessionLocal() as s:
        prods = await get_products_by_category(s, cid)
        if not prods:
            await message.answer(f"{pe('warning')} Нет товаров.", parse_mode="HTML"); return
        listing = "\n".join(f"{p.id}: {p.name} ({p.quantity} шт.)" for p in prods)
    await state.update_data(category_id=cid)
    await message.answer(f"{pe('box')} <b>Товары:</b>\n{listing}\n\nID товара:", parse_mode="HTML")
    await state.set_state(DeleteLines.product_id)

@router.message(DeleteLines.product_id)
async def dl_prod(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        pid = int(message.text.strip())
    except Exception:
        await message.answer(f"{pe('warning')} Нужно число.", parse_mode="HTML"); return
    async with AsyncSessionLocal() as s:
        prod = await s.get(Product, pid)
        if not prod or not prod.content:
            await message.answer(f"{pe('warning')} У товара нет контента.", parse_mode="HTML"); return
        lines = [l for l in prod.content.split("\n") if l.strip()]
        preview = "\n".join(f"{i+1}: {l}" for i, l in enumerate(lines[:15]))
        if len(lines) > 15:
            preview += f"\n... ещё {len(lines)-15}"
    await state.update_data(product_id=pid)
    await message.answer(
        f"{pe('books')} Строк: {len(lines)}\n\n<code>{preview}</code>\n\n"
        f"Введи номера через запятую, например <code>1,3,5</code>, "
        f"или <code>всё кроме 1,2,3</code>",
        parse_mode="HTML"
    )
    await state.set_state(DeleteLines.lines)

@router.message(DeleteLines.lines)
async def dl_exec(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    data = await state.get_data()
    inp = message.text.strip()
    async with AsyncSessionLocal() as s:
        prod = await s.get(Product, data["product_id"])
        if not prod:
            await message.answer(f"{pe('ban')} Не найдено.", parse_mode="HTML"); await state.clear(); return
        lines = [l for l in prod.content.split("\n") if l.strip()]
        try:
            if inp.lower().startswith("всё кроме"):
                keep = {int(n.strip()) for n in inp.lower().replace("всё кроме", "").strip().split(",")}
                new_lines = [l for i, l in enumerate(lines, 1) if i in keep]
            else:
                remove = {int(n.strip()) for n in inp.split(",")}
                new_lines = [l for i, l in enumerate(lines, 1) if i not in remove]
        except Exception:
            await message.answer(f"{pe('warning')} Неверный формат номеров.", parse_mode="HTML"); return
        prod.content = "\n".join(new_lines) or None
        prod.quantity = len(new_lines)
        await s.commit()
    await message.answer(f"{pe('check')} Осталось: {len(new_lines)} строк.", parse_mode="HTML", reply_markup=back_kb())
    await state.clear()

# ── КАТЕГОРИИ ─────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "a_add_cat")
async def add_cat(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await safe_edit(callback.message, f"{pe('folder')} Название новой категории:", back_kb())
    await state.set_state(AddCategory.name)
    await callback.answer()

@router.message(AddCategory.name)
async def ac_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    await state.update_data(name=message.text)
    await message.answer("ID родительской категории (0 = корневая):")
    await state.set_state(AddCategory.parent_id)

@router.message(AddCategory.parent_id)
async def ac_parent(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        pid = int(message.text.strip())
    except Exception:
        await message.answer(f"{pe('warning')} Нужно число.", parse_mode="HTML"); return
    data = await state.get_data()
    async with AsyncSessionLocal() as s:
        if pid != 0 and not await s.get(Category, pid):
            await message.answer(f"{pe('ban')} Категория с таким ID не найдена.", parse_mode="HTML"); return
        s.add(Category(name=data["name"], parent_id=pid if pid != 0 else None))
        await s.commit()
    await message.answer(f"{pe('check')} Категория «{data['name']}» создана.", parse_mode="HTML", reply_markup=back_kb())
    await state.clear()

@router.callback_query(F.data == "a_del_prod")
async def del_prod(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        cats = await get_categories(s)
        if not cats:
            await safe_edit(callback.message, f"{pe('warning')} Нет категорий.", back_kb()); await callback.answer(); return
        listing = "\n".join(f"{c.id}: {c.name}" for c in cats)
    await safe_edit(callback.message, f"{pe('folder')} <b>Категории:</b>\n{listing}\n\nID категории:", back_kb())
    await state.set_state(DelProduct.category_id)
    await callback.answer()

@router.message(DelProduct.category_id)
async def dp_cat(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        cid = int(message.text.strip())
    except Exception:
        await message.answer(f"{pe('warning')} Нужно число.", parse_mode="HTML"); return
    async with AsyncSessionLocal() as s:
        prods = await get_products_by_category(s, cid)
        if not prods:
            await message.answer(f"{pe('warning')} Нет товаров.", parse_mode="HTML"); return
        listing = "\n".join(f"{p.id}: {p.name}" for p in prods)
    await state.update_data(category_id=cid)
    await message.answer(f"{pe('box')} <b>Товары:</b>\n{listing}\n\nID товара для удаления:", parse_mode="HTML")
    await state.set_state(DelProduct.product_id)

@router.message(DelProduct.product_id)
async def dp_exec(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        pid = int(message.text.strip())
    except Exception:
        await message.answer(f"{pe('warning')} Нужно число.", parse_mode="HTML"); return
    async with AsyncSessionLocal() as s:
        prod = await s.get(Product, pid)
        if not prod:
            await message.answer(f"{pe('ban')} Не найдено.", parse_mode="HTML"); await state.clear(); return
        name = prod.name
        await s.delete(prod)
        await s.commit()
    await message.answer(f"{pe('check')} «{name}» удалён.", parse_mode="HTML", reply_markup=back_kb())
    await state.clear()

@router.callback_query(F.data == "a_del_cat")
async def del_cat(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        cats = await get_categories(s)
        if not cats:
            await safe_edit(callback.message, f"{pe('warning')} Нет категорий.", back_kb()); await callback.answer(); return
        listing = "\n".join(f"{c.id}: {c.name}" for c in cats)
    await safe_edit(callback.message, f"{pe('folder')} <b>Категории:</b>\n{listing}\n\nID для удаления:", back_kb())
    await state.set_state(DelCategory.category_id)
    await callback.answer()

@router.message(DelCategory.category_id)
async def dc_exec(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        cid = int(message.text.strip())
    except Exception:
        await message.answer(f"{pe('warning')} Нужно число.", parse_mode="HTML"); return
    async with AsyncSessionLocal() as s:
        cat = await s.get(Category, cid)
        if not cat:
            await message.answer(f"{pe('ban')} Не найдено.", parse_mode="HTML"); await state.clear(); return
        name = cat.name
        await s.delete(cat)
        await s.commit()
    await message.answer(f"{pe('check')} «{name}» удалена.", parse_mode="HTML", reply_markup=back_kb())
    await state.clear()

# ── ПРОМОКОДЫ ─────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "a_promo_add")
async def promo_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await safe_edit(callback.message, f"{pe('gift')} Код промокода (например SALE2026):", back_kb())
    await state.set_state(PromoAdd.code)
    await callback.answer()

@router.message(PromoAdd.code)
async def pa_code(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    await state.update_data(code=message.text.strip().upper())
    await message.answer(f"{pe('wallet')} Бонус в $:", parse_mode="HTML")
    await state.set_state(PromoAdd.amount)

@router.message(PromoAdd.amount)
async def pa_amt(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        amt = float(message.text.replace(",", ".").strip())
        if amt <= 0: raise ValueError
    except Exception:
        await message.answer(f"{pe('warning')} Нужно положительное число.", parse_mode="HTML"); return
    await state.update_data(amount=amt)
    await message.answer("Макс. активаций (0 = безлимит):")
    await state.set_state(PromoAdd.max_uses)

@router.message(PromoAdd.max_uses)
async def pa_max(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        mx = int(message.text.strip())
        if mx < 0: raise ValueError
    except Exception:
        await message.answer(f"{pe('warning')} Нужно целое число.", parse_mode="HTML"); return
    await state.update_data(max_uses=None if mx == 0 else mx)
    await message.answer("Срок действия в днях (0 = бессрочно):")
    await state.set_state(PromoAdd.days)

@router.message(PromoAdd.days)
async def pa_exp(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        days = int(message.text.strip())
        if days < 0: raise ValueError
    except Exception:
        await message.answer(f"{pe('warning')} Нужно целое число.", parse_mode="HTML"); return
    data = await state.get_data()
    expires = datetime.utcnow() + timedelta(days=days) if days > 0 else None
    async with AsyncSessionLocal() as s:
        if await s.get(Promocode, data["code"]):
            await message.answer(f"{pe('ban')} Такой промокод уже существует.", parse_mode="HTML")
            await state.clear(); return
        s.add(Promocode(
            code=data["code"], bonus_amount=data["amount"],
            max_activations=data.get("max_uses"), expires_at=expires
        ))
        await s.commit()
    await message.answer(f"{pe('check')} Промокод «{data['code']}» создан!", parse_mode="HTML", reply_markup=back_kb())
    await state.clear()

@router.callback_query(F.data == "a_promo_del")
async def promo_del(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await safe_edit(callback.message, f"{pe('trash')} Код промокода для удаления:", back_kb())
    await state.set_state(PromoDel.code)
    await callback.answer()

@router.message(PromoDel.code)
async def pd_exec(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    async with AsyncSessionLocal() as s:
        p = await s.get(Promocode, message.text.strip().upper())
        if not p:
            await message.answer(f"{pe('ban')} Не найден.", parse_mode="HTML"); await state.clear(); return
        await s.delete(p)
        await s.commit()
    await message.answer(f"{pe('check')} Удалён.", parse_mode="HTML", reply_markup=back_kb())
    await state.clear()

@router.callback_query(F.data == "a_promo_list")
async def promo_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        promos = (await s.execute(select(Promocode))).scalars().all()
    if not promos:
        await callback.answer("Пусто.", show_alert=True); return
    lines = [f"{pe('gift')} <b>Промокоды:</b>\n"]
    for p in promos:
        exp = p.expires_at.strftime("%d.%m.%Y") if p.expires_at else "∞"
        lines.append(f"{'✅' if p.is_active else '❌'} <code>{p.code}</code> +{p.bonus_amount}$ "
                     f"{p.used_count}/{p.max_activations or '∞'} до {exp}")
    await callback.message.answer("\n".join(lines), parse_mode="HTML", reply_markup=back_kb())
    await callback.answer()

# ── ПОЛЬЗОВАТЕЛИ ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "a_user_find")
async def user_search(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await safe_edit(callback.message, f"{pe('search')} Введи ID пользователя:", back_kb())
    await state.set_state(UserFind.user_id)
    await callback.answer()

@router.message(UserFind.user_id)
async def us_show(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        uid = int(message.text.strip())
    except Exception:
        await message.answer(f"{pe('warning')} Нужно число.", parse_mode="HTML"); return
    async with AsyncSessionLocal() as s:
        user = await s.get(User, uid)
        if not user:
            await message.answer(f"{pe('ban')} Пользователь {uid} не найден.", parse_mode="HTML")
            await state.clear(); return
        buys = len((await s.execute(select(Purchase).where(Purchase.user_id == uid))).scalars().all())
    await message.answer(
        f"{pe('user')} <code>{user.user_id}</code> @{user.username or '—'}\n"
        f"{pe('wallet')} Баланс: {user.balance:.2f}$\n"
        f"{pe('briefcase')} Покупок: {buys}  |  Потрачено: {user.total_spent:.2f}$\n"
        f"{pe('star2')} Кэшбек: {user.cashback_pct}%\n"
        f"{pe('link')} Рефералов: {user.ref_count}\n"
        f"{'🚫 Бан: ' + (user.ban_reason or '—') if user.is_banned else '✅ Активен'}\n"
        f"{pe('clock')} Рег.: {user.registered_at.strftime('%d.%m.%Y')}",
        parse_mode="HTML", reply_markup=back_kb()
    )
    await state.clear()

@router.callback_query(F.data == "a_user_bal")
async def user_bal(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await safe_edit(callback.message, f"{pe('wallet')} ID пользователя:", back_kb())
    await state.set_state(UserBal.user_id)
    await callback.answer()

@router.message(UserBal.user_id)
async def ub_uid(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        uid = int(message.text.strip())
    except Exception:
        await message.answer(f"{pe('warning')} Нужно число.", parse_mode="HTML"); return
    async with AsyncSessionLocal() as s:
        user = await s.get(User, uid)
        if not user:
            await message.answer(f"{pe('ban')} Не найден.", parse_mode="HTML"); await state.clear(); return
        bal = user.balance
    await state.update_data(user_id=uid)
    await message.answer(f"Текущий баланс: {bal:.2f}$\nВведи изменение (+10, -5 или =100):")
    await state.set_state(UserBal.amount)

@router.message(UserBal.amount)
async def ub_set(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    data = await state.get_data()
    txt = message.text.strip()
    async with AsyncSessionLocal() as s:
        user = await s.get(User, data["user_id"])
        if not user:
            await message.answer(f"{pe('ban')} Не найден.", parse_mode="HTML"); await state.clear(); return
        try:
            if txt.startswith("+"):
                user.balance += float(txt[1:])
            elif txt.startswith("-"):
                user.balance -= float(txt[1:])
            elif txt.startswith("="):
                user.balance = float(txt[1:])
            else:
                raise ValueError
        except Exception:
            await message.answer(f"{pe('warning')} Формат: +10 / -5 / =100", parse_mode="HTML"); return
        await s.commit()
        await message.answer(f"{pe('check')} Баланс: {user.balance:.2f}$", parse_mode="HTML", reply_markup=back_kb())
    await state.clear()

@router.callback_query(F.data == "user_ban")
async def user_ban_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await safe_edit(callback.message, f"{pe('ban')} ID пользователя (бан или разбан):", back_kb())
    await state.set_state(UserBan.user_id)
    await callback.answer()

@router.message(UserBan.user_id)
async def ban_uid(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        uid = int(message.text.strip())
    except Exception:
        await message.answer(f"{pe('warning')} Нужно число (ID пользователя).", parse_mode="HTML"); return
    async with AsyncSessionLocal() as s:
        user = await s.get(User, uid)
        if not user:
            await message.answer(f"{pe('ban')} Пользователь {uid} не найден.", parse_mode="HTML")
            await state.clear(); return
        if user.is_banned:
            user.is_banned = False
            user.ban_reason = None
            await s.commit()
            await message.answer(f"{pe('check')} Пользователь {uid} разбанен.", parse_mode="HTML", reply_markup=back_kb())
            try:
                await message.bot.send_message(uid, f"{pe('unlock')} Вы разблокированы!", parse_mode="HTML")
            except Exception: pass
            await state.clear()
            return
    await state.update_data(user_id=uid)
    await message.answer(f"{pe('warning')} Причина блокировки:", parse_mode="HTML")
    await state.set_state(UserBan.reason)

@router.message(UserBan.reason)
async def ban_exec(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    data = await state.get_data()
    async with AsyncSessionLocal() as s:
        user = await s.get(User, data["user_id"])
        if not user:
            await message.answer(f"{pe('ban')} Не найден.", parse_mode="HTML"); await state.clear(); return
        user.is_banned = True
        user.ban_reason = message.text
        await s.commit()
    try:
        from keyboards.kb import banned_kb
        await message.bot.send_message(
            data["user_id"],
            f"{pe('ban')} Вы заблокированы.\nПричина: {message.text}",
            parse_mode="HTML", reply_markup=banned_kb()
        )
    except Exception: pass
    await message.answer(f"{pe('check')} Пользователь {data['user_id']} заблокирован.", parse_mode="HTML", reply_markup=back_kb())
    await state.clear()

@router.callback_query(F.data == "user_cashback")
async def user_cb_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await safe_edit(callback.message, f"{pe('star')} ID пользователя:", back_kb())
    await state.set_state(UserCashback.user_id)
    await callback.answer()

@router.message(UserCashback.user_id)
async def ucb_uid(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        uid = int(message.text.strip())
    except Exception:
        await message.answer(f"{pe('warning')} Нужно число.", parse_mode="HTML"); return
    async with AsyncSessionLocal() as s:
        if not await s.get(User, uid):
            await message.answer(f"{pe('ban')} Не найден.", parse_mode="HTML"); await state.clear(); return
    await state.update_data(user_id=uid)
    await message.answer("Новый % кэшбека (например 2.5):")
    await state.set_state(UserCashback.pct)

@router.message(UserCashback.pct)
async def ucb_set(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    if await is_interrupt(message):
        await state.clear(); return
    try:
        pct = float(message.text.replace(",", ".").strip())
        if pct < 0: raise ValueError
    except Exception:
        await message.answer(f"{pe('warning')} Нужно положительное число.", parse_mode="HTML"); return
    data = await state.get_data()
    async with AsyncSessionLocal() as s:
        user = await s.get(User, data["user_id"])
        if not user:
            await message.answer(f"{pe('ban')} Не найден.", parse_mode="HTML"); await state.clear(); return
        user.cashback_pct = pct
        await s.commit()
    await message.answer(f"{pe('check')} Кэшбек пользователя {data['user_id']}: {pct}%", parse_mode="HTML", reply_markup=back_kb())
    await state.clear()

# ── ЗАМЕНЫ / РАЗБЛОКИРОВКИ (списки) ──────────────────────────────────────────
@router.callback_query(F.data == "admin_replaces")
async def admin_replaces(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        reqs = (await s.execute(select(ReplaceRequest).where(ReplaceRequest.status == "pending").limit(20))).scalars().all()
    if not reqs:
        await callback.answer("Заявок нет.", show_alert=True); return
    lines = [f"{pe('hammer')} <b>Замены (pending):</b>\n"]
    for r in reqs:
        lines.append(f"#{r.id} | {r.user_id} | {r.created_at.strftime('%d.%m %H:%M')}")
    await callback.message.answer("\n".join(lines), parse_mode="HTML", reply_markup=back_kb())
    await callback.answer()

@router.callback_query(F.data == "admin_unbans")
async def admin_unbans(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    async with AsyncSessionLocal() as s:
        reqs = (await s.execute(select(UnbanRequest).where(UnbanRequest.status == "pending").limit(20))).scalars().all()
    if not reqs:
        await callback.answer("Заявок нет.", show_alert=True); return
    lines = [f"{pe('unlock')} <b>Разблокировки (pending):</b>\n"]
    for r in reqs:
        lines.append(f"#{r.id} | {r.user_id} | {r.created_at.strftime('%d.%m %H:%M')}")
    await callback.message.answer("\n".join(lines), parse_mode="HTML", reply_markup=back_kb())
    await callback.answer()
