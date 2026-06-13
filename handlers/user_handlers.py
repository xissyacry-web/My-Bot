import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
from sqlalchemy import select

from database.database import AsyncSessionLocal
from database.models import User, Invoice, Promocode, Purchase, Product, UnbanRequest, UserDiscount, StockNotify, Review
from keyboards.reply import remove_keyboard
from keyboards.inline import (
    categories_kb, products_kb, product_actions_kb, profile_kb,
    payment_kb, history_kb, purchase_detail_kb, review_rating_kb,
    unban_confirm_kb, amount_kb, crypto_assets_kb, main_menu_inline_kb,
    back_to_main_kb, replace_action_kb, unban_action_kb, banned_kb, _btn
)
from services.user_service import get_user, create_user
from services.product_service import get_categories, get_products_by_category, buy_product
from services.payment_service import create_invoice, get_invoice
from services.replace_service import create_replace_request
from services.log_service import log_purchase, log_register, log_refill, log_promo, log_review
from utils.states import (
    ReplenishBalance, PromocodeInput, BuyProduct,
    UnbanProcess, ReplaceRequestStates, ReviewStates
)
from config import ADMIN_IDS, pe, pe_coin, pe_num, REF_BONUS, BOT_USERNAME

router = Router()

# ── HELPERS ───────────────────────────────────────────────────────────────────
async def get_active_discount(session, user_id):
    return (await session.execute(
        select(UserDiscount).where(
            UserDiscount.user_id == user_id,
            UserDiscount.expires_at > datetime.utcnow()
        )
    )).scalar_one_or_none()

async def send_main_menu(target, text: str = None):
    menu_text = f"{pe('crown')} <b>Главное меню</b>\n\nВыбери раздел:"
    if isinstance(target, Message):
        if text:
            await target.answer(text, parse_mode="HTML", reply_markup=remove_keyboard())
        await target.answer(menu_text, parse_mode="HTML", reply_markup=main_menu_inline_kb())
    elif isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(menu_text, parse_mode="HTML", reply_markup=main_menu_inline_kb())
        except Exception:
            await target.message.answer(menu_text, parse_mode="HTML", reply_markup=main_menu_inline_kb())

# ── START ─────────────────────────────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    args = message.text.split()
    ref_code = None
    if len(args) > 1 and args[1].startswith("ref_"):
        ref_code = args[1][4:]

    async with AsyncSessionLocal() as s:
        user = await get_user(s, message.from_user.id)
        if not user:
            ref_by = None
            if ref_code:
                referrer = (await s.execute(
                    select(User).where(User.ref_code == ref_code)
                )).scalar_one_or_none()
                if referrer and referrer.user_id != message.from_user.id:
                    ref_by = referrer.user_id
                    referrer.balance += REF_BONUS
                    referrer.ref_count += 1
                    await s.commit()
                    try:
                        await message.bot.send_message(
                            ref_by,
                            f"{pe('gift')} По вашей ссылке зарегистрировался новый пользователь!\n"
                            f"{pe('wallet')} +{REF_BONUS}$ на баланс.",
                            parse_mode="HTML"
                        )
                    except Exception: pass
            await create_user(s, message.from_user.id, message.from_user.username, referred_by=ref_by)
            await log_register(message.bot, message.from_user.id, message.from_user.username, ref_by)

    await send_main_menu(message, f"{pe('crown')} Добро пожаловать!")

# ── ЛЮБОЕ НЕИЗВЕСТНОЕ СООБЩЕНИЕ → МЕНЮ ───────────────────────────────────────
@router.message(F.text & ~F.text.startswith("/"))
async def unknown_message(message: Message, state: FSMContext):
    current = await state.get_state()
    if current:
        return  # если в состоянии FSM — не мешаем
    await send_main_menu(message)

# ── ГЛАВНОЕ МЕНЮ КНОПКИ ───────────────────────────────────────────────────────
@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await send_main_menu(callback)
    await callback.answer()

@router.callback_query(F.data == "main_catalog")
async def main_catalog(callback: CallbackQuery):
    async with AsyncSessionLocal() as s:
        cats = await get_categories(s, parent_id=None)
    if cats:
        try:
            await callback.message.edit_text(
                f"{pe('folder')} <b>Каталог</b>", parse_mode="HTML",
                reply_markup=categories_kb(cats)
            )
        except Exception:
            await callback.message.answer(
                f"{pe('folder')} <b>Каталог</b>", parse_mode="HTML",
                reply_markup=categories_kb(cats)
            )
    else:
        await callback.answer("Каталог пуст", show_alert=True)
    await callback.answer()

@router.callback_query(F.data == "main_profile")
async def main_profile(callback: CallbackQuery):
    await show_profile(callback)
    await callback.answer()

@router.callback_query(F.data == "main_replace")
async def main_replace_cb(callback: CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as s:
        exists = (await s.execute(
            select(Purchase).where(Purchase.user_id == callback.from_user.id, Purchase.status == "completed")
        )).first()
    if not exists:
        await callback.answer("Нет завершённых покупок.", show_alert=True); return
    await callback.message.answer(f"{pe('hammer')} Укажи номер лога и время покупки:", parse_mode="HTML")
    await state.set_state(ReplaceRequestStates.log_time)
    await callback.answer()

@router.callback_query(F.data == "main_support")
async def main_support(callback: CallbackQuery):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    b.add(_btn("Главное меню", cb="back_to_main", emoji_key="home"))
    await callback.message.answer(
        f"{pe('info')} <b>Поддержка</b>\n\n@XissyaSup",
        parse_mode="HTML", reply_markup=b.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "main_discount")
async def main_discount(callback: CallbackQuery, state: FSMContext):
    await spin_discount_action(callback.from_user.id, callback.from_user.username, callback.message, callback.bot)
    await callback.answer()

# ── КАТАЛОГ ───────────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("cat_"))
async def category_cb(callback: CallbackQuery):
    cat_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as s:
        from database.models import Category
        cat = await s.get(Category, cat_id)
        if not cat: await callback.answer("Не найдено", show_alert=True); return
        subcats = await get_categories(s, parent_id=cat_id)
        if subcats:
            await callback.message.edit_text(
                f"{pe('folder')} <b>{cat.name}</b>", parse_mode="HTML",
                reply_markup=categories_kb(subcats)
            )
        else:
            products = await get_products_by_category(s, cat_id)
            if products:
                await callback.message.edit_text(
                    f"{pe('folder')} <b>{cat.name}</b>\n\nВыбери товар:",
                    parse_mode="HTML", reply_markup=products_kb(products)
                )
            else:
                await callback.answer("Товаров нет", show_alert=True)
    await callback.answer()

@router.callback_query(F.data == "back_to_categories")
async def back_cats(callback: CallbackQuery):
    async with AsyncSessionLocal() as s:
        cats = await get_categories(s, parent_id=None)
    if cats:
        await callback.message.edit_text(
            f"{pe('folder')} <b>Каталог</b>", parse_mode="HTML",
            reply_markup=categories_kb(cats)
        )
    else:
        await callback.message.edit_text("Каталог пуст")
    await callback.answer()

@router.callback_query(F.data.startswith("buy_"))
async def show_product(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as s:
        product = await s.get(Product, product_id)
        if not product: await callback.answer("Не найдено", show_alert=True); return
        disc = await get_active_discount(s, callback.from_user.id)
        qty = "∞" if product.quantity == 0 else str(product.quantity)
        avg = f"⭐ {product.rating_sum/product.rating_count:.1f} ({product.rating_count})" if product.rating_count else "нет отзывов"
        if disc:
            final = round(product.price * (1 - disc.percent / 100), 2)
            price_line = f"💰 <s>{product.price}$</s> → <b>{final}$</b> (-{disc.percent}%)"
        else:
            price_line = f"💰 <b>{product.price}$</b>"
        out_of_stock = not product.is_available
        text = (
            f"{pe('box')} <b>{product.name}</b>\n\n"
            f"{product.description or 'Без описания'}\n\n"
            f"{price_line}\n"
            f"{pe('clock')} В наличии: {'нет' if out_of_stock else qty + ' шт.'}\n"
            f"{pe('star')} Рейтинг: {avg}"
        )
    await callback.message.answer(
        text, parse_mode="HTML",
        reply_markup=product_actions_kb(product_id, out_of_stock=out_of_stock)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_buy_"))
async def ask_amount(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[2])
    await state.update_data(product_id=product_id)
    await state.set_state(BuyProduct.amount)
    await callback.message.answer("Введи количество:", reply_markup=amount_kb(product_id))
    await callback.answer()

@router.callback_query(F.data.startswith("quickbuy_"))
async def quickbuy(callback: CallbackQuery, state: FSMContext):
    _, product_id, n = callback.data.split("_")
    await do_buy(callback.from_user.id, callback.from_user.username,
                 int(product_id), int(n), callback.message, callback.bot)
    await state.clear()
    await callback.answer()

@router.message(BuyProduct.amount)
async def buy_amount_msg(message: Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount <= 0: raise ValueError
    except Exception:
        await message.answer("Введи целое положительное число."); return
    data = await state.get_data()
    await do_buy(message.from_user.id, message.from_user.username,
                 data["product_id"], amount, message, message.bot)
    await state.clear()

async def do_buy(user_id, username, product_id, amount, msg_obj, bot):
    async with AsyncSessionLocal() as s:
        disc = await get_active_discount(s, user_id)
        discount_pct = disc.percent if disc else 0
        result = await buy_product(s, user_id, product_id, amount, discount_pct)
        if result["success"]:
            cb_line = f"\n{pe('star')} Кэшбек: +{result['cashback']:.4f}$" if result.get("cashback") else ""
            await msg_obj.answer(
                f"{pe('check')} <b>Куплено {amount} шт.</b>\n"
                f"{pe('wallet')} {result['total_price']:.2f}$  |  баланс: {result['balance']:.2f}${cb_line}",
                parse_mode="HTML"
            )
            if result.get("content"):
                await msg_obj.answer(
                    f"{pe('books')} <b>Товар:</b>\n\n<code>{result['content']}</code>",
                    parse_mode="HTML"
                )
            if result.get("file_id"):
                try: await bot.send_document(user_id, result["file_id"])
                except Exception: pass
            await log_purchase(bot, user_id, username, result["product_name"],
                               amount, result["total_price"], result.get("cashback", 0),
                               result.get("selected_lines", []))
        else:
            await msg_obj.answer(f"{pe('warning')} {result['error']}", parse_mode="HTML")

@router.callback_query(F.data.startswith("notify_"))
async def subscribe_stock(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    async with AsyncSessionLocal() as s:
        exists = (await s.execute(
            select(StockNotify).where(StockNotify.user_id == user_id, StockNotify.product_id == product_id)
        )).scalar_one_or_none()
        if exists:
            await callback.answer("Вы уже подписаны!", show_alert=True); return
        s.add(StockNotify(user_id=user_id, product_id=product_id))
        await s.commit()
    await callback.answer(f"🔔 Уведомим когда появится!", show_alert=True)

# ── ПРОФИЛЬ ───────────────────────────────────────────────────────────────────
async def show_profile(target):
    user_id = target.from_user.id if isinstance(target, CallbackQuery) else target.from_user.id
    async with AsyncSessionLocal() as s:
        user = await get_user(s, user_id)
        if not user:
            user = await create_user(s, user_id)
        disc = await get_active_discount(s, user_id)
        buys_count = len((await s.execute(
            select(Purchase).where(Purchase.user_id == user_id)
        )).scalars().all())
    days = (datetime.utcnow() - user.registered_at).days
    disc_line = ""
    if disc:
        h = int((disc.expires_at - datetime.utcnow()).total_seconds() // 3600)
        disc_line = f"\n{pe('star')} Скидка: <b>{disc.percent}%</b> (ещё {h}ч.)"
    text = (
        f"{pe('user')} <b>Профиль</b>\n\n"
        f"ID: <code>{user.user_id}</code>\n"
        f"@{user.username or '—'}\n"
        f"{pe('wallet')} Баланс: <b>{user.balance:.2f}$</b>\n"
        f"{pe('briefcase')} Покупок: {buys_count}\n"
        f"{pe('chart')} Потрачено: {user.total_spent:.2f}$\n"
        f"{pe('star2')} Кэшбек: {user.cashback_pct}%\n"
        f"{pe('link')} Рефералов: {user.ref_count}\n"
        f"{pe('clock')} Дней: {days}"
        f"{disc_line}"
    )
    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text, parse_mode="HTML", reply_markup=profile_kb())
        except Exception:
            await target.message.answer(text, parse_mode="HTML", reply_markup=profile_kb())
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=profile_kb())

@router.callback_query(F.data == "profile_back")
async def profile_back(callback: CallbackQuery):
    await show_profile(callback)
    await callback.answer()

@router.callback_query(F.data == "profile_ref")
async def ref_link(callback: CallbackQuery):
    async with AsyncSessionLocal() as s:
        user = await get_user(s, callback.from_user.id)
    # Реф ссылка: https://t.me/XissyaLogBot?start=ref_{ref_code пользователя}
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{user.ref_code}"
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    b.add(_btn("Назад", cb="profile_back", emoji_key="down"))
    await callback.message.answer(
        f"{pe('link')} <b>Реферальная ссылка</b>\n\n"
        f"<code>{link}</code>\n\n"
        f"За каждого приглашённого — бонус!\n"
        f"{pe('users')} Приглашено: {user.ref_count}",
        parse_mode="HTML", reply_markup=b.as_markup()
    )
    await callback.answer()

# ── ПОПОЛНЕНИЕ ────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "profile_topup")
async def topup_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        f"{pe('wallet')} Выбери валюту:", parse_mode="HTML",
        reply_markup=crypto_assets_kb()
    )
    await state.set_state(ReplenishBalance.asset)
    await callback.answer()

@router.callback_query(F.data == "cancel_topup")
async def cancel_topup(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try: await callback.message.delete()
    except Exception: pass
    await callback.answer("Отменено")

@router.callback_query(ReplenishBalance.asset, F.data.startswith("asset_"))
async def topup_asset(callback: CallbackQuery, state: FSMContext):
    asset = callback.data.split("_")[1]
    await state.update_data(asset=asset)
    await state.set_state(ReplenishBalance.amount)
    await callback.message.edit_text(
        f"{pe('wallet')} Валюта: <b>{asset}</b>\n\nВведи сумму в $:",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(ReplenishBalance.amount)
async def topup_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        if amount <= 0: raise ValueError
    except Exception:
        await message.answer("Введи положительное число."); return
    data = await state.get_data()
    asset = data.get("asset", "USDT")
    try:
        inv = await create_invoice(amount, f"Пополнение #{message.from_user.id}", asset=asset)
    except Exception as e:
        await message.answer(f"{pe('warning')} {e}", parse_mode="HTML")
        await state.clear(); return
    async with AsyncSessionLocal() as s:
        from database.models import Invoice
        s.add(Invoice(user_id=message.from_user.id, invoice_id=inv["invoice_id"], amount=amount, asset=asset))
        await s.commit()
    await message.answer(
        f"{pe('wallet')} Счёт на <b>{amount}$ ({asset})</b>\n\nОплати и нажми «Проверить».",
        parse_mode="HTML", reply_markup=payment_kb(inv["pay_url"])
    )
    await state.clear()

@router.callback_query(F.data == "check_payment")
async def check_payment(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with AsyncSessionLocal() as s:
        from database.models import Invoice
        inv = (await s.execute(
            select(Invoice).where(Invoice.user_id == user_id, Invoice.status == "active")
            .order_by(Invoice.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        if not inv: await callback.answer("Нет активных счетов.", show_alert=True); return
        data = await get_invoice(inv.invoice_id)
        if data and data["status"] == "paid":
            inv.status = "paid"
            user = await s.get(User, user_id)
            user.balance += inv.amount
            await s.commit()
            await callback.message.answer(
                f"{pe('check')} Зачислено <b>{inv.amount:.2f}$ ({inv.asset})</b>",
                parse_mode="HTML"
            )
            await log_refill(callback.bot, user_id, callback.from_user.username, inv.amount, inv.asset)
        elif data and data["status"] == "expired":
            inv.status = "expired"
            await s.commit()
            await callback.message.answer(f"{pe('clock')} Счёт истёк.", parse_mode="HTML")
        else:
            await callback.answer("Оплата не поступила.", show_alert=True)
    await callback.answer()

# ── ПРОМОКОД ──────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "profile_promo")
async def promo_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(f"{pe('gift')} Введи промокод:", parse_mode="HTML")
    await state.set_state(PromocodeInput.code)
    await callback.answer()

@router.message(PromocodeInput.code)
async def promo_apply(message: Message, state: FSMContext):
    code = message.text.strip()
    async with AsyncSessionLocal() as s:
        user = await get_user(s, message.from_user.id)
        promo = await s.get(Promocode, code)
        used = [c.strip() for c in user.used_promocodes.split(",") if c.strip()]
        if code in used:
            await message.answer(f"{pe('ban')} Уже использован.", parse_mode="HTML")
        elif not promo or not promo.is_active:
            await message.answer(f"{pe('ban')} Недействителен.", parse_mode="HTML")
        elif promo.expires_at and promo.expires_at < datetime.utcnow():
            await message.answer(f"{pe('clock')} Истёк.", parse_mode="HTML")
        elif promo.max_activations and promo.used_count >= promo.max_activations:
            await message.answer(f"{pe('ban')} Лимит исчерпан.", parse_mode="HTML")
        else:
            user.balance += promo.bonus_amount
            promo.used_count += 1
            user.used_promocodes = ",".join(used + [code])
            await s.commit()
            await message.answer(f"{pe('gift')} <b>+{promo.bonus_amount:.2f}$</b>!", parse_mode="HTML")
            await log_promo(message.bot, message.from_user.id, message.from_user.username, code, promo.bonus_amount)
    await state.clear()

# ── ИСТОРИЯ ───────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "profile_history")
async def profile_history(callback: CallbackQuery):
    async with AsyncSessionLocal() as s:
        purchases = (await s.execute(
            select(Purchase).where(Purchase.user_id == callback.from_user.id)
            .order_by(Purchase.purchased_at.desc()).limit(20)
        )).scalars().all()
    if not purchases: await callback.answer("Покупок нет.", show_alert=True); return
    try:
        await callback.message.edit_text(
            f"{pe('books')} <b>Покупки</b>", parse_mode="HTML",
            reply_markup=history_kb(purchases)
        )
    except Exception:
        await callback.message.answer(
            f"{pe('books')} <b>Покупки</b>", parse_mode="HTML",
            reply_markup=history_kb(purchases)
        )
    await callback.answer()

@router.callback_query(F.data.startswith("hist_"))
async def purchase_detail(callback: CallbackQuery):
    pid = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as s:
        p = await s.get(Purchase, pid)
        if not p: await callback.answer("Не найдено", show_alert=True); return
        product = await s.get(Product, p.product_id)
        pname = product.name if product else "удалён"
        existing_review = (await s.execute(
            select(Review).where(Review.purchase_id == pid)
        )).scalar_one_or_none()
    cb_line = f"\n{pe('star')} Кэшбек: +{p.cashback:.4f}$" if p.cashback else ""
    await callback.message.edit_text(
        f"{pe('box')} <b>{pname}</b>\n"
        f"×{p.amount} шт.  |  {pe('wallet')} {p.price:.2f}${cb_line}\n"
        f"{pe('clock')} {p.purchased_at.strftime('%d.%m.%Y %H:%M')}",
        parse_mode="HTML",
        reply_markup=purchase_detail_kb(pid, not existing_review)
    )
    await callback.answer()

# ── ОТЗЫВЫ ────────────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("leave_review_"))
async def leave_review(callback: CallbackQuery, state: FSMContext):
    purchase_id = int(callback.data.split("_")[2])
    await state.update_data(purchase_id=purchase_id)
    await state.set_state(ReviewStates.rating)
    await callback.message.answer(f"{pe('star')} Оцени товар:", parse_mode="HTML",
                                   reply_markup=review_rating_kb(purchase_id))
    await callback.answer()

@router.callback_query(ReviewStates.rating, F.data.startswith("rate_"))
async def review_rating_cb(callback: CallbackQuery, state: FSMContext):
    _, purchase_id, rating = callback.data.split("_")
    await state.update_data(rating=int(rating))
    await state.set_state(ReviewStates.text)
    await callback.message.answer("Напиши отзыв (или «-» пропустить):")
    await callback.answer()

@router.message(ReviewStates.text)
async def review_text(message: Message, state: FSMContext):
    data = await state.get_data()
    text_review = None if message.text.strip() == "-" else message.text.strip()
    async with AsyncSessionLocal() as s:
        p = await s.get(Purchase, data["purchase_id"])
        if not p: await message.answer("Не найдено."); await state.clear(); return
        product = await s.get(Product, p.product_id)
        s.add(Review(user_id=message.from_user.id, product_id=p.product_id,
                     purchase_id=p.id, rating=data["rating"], text=text_review))
        product.rating_sum += data["rating"]
        product.rating_count += 1
        await s.commit()
    await message.answer(f"{pe('check')} Отзыв сохранён! {'⭐'*data['rating']}", parse_mode="HTML")
    await log_review(message.bot, message.from_user.id, message.from_user.username,
                     product.name if product else "", data["rating"], text_review)
    await state.clear()

@router.callback_query(F.data.startswith("reviews_"))
async def show_reviews(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as s:
        product = await s.get(Product, product_id)
        reviews = (await s.execute(
            select(Review).where(Review.product_id == product_id)
            .order_by(Review.created_at.desc()).limit(10)
        )).scalars().all()
    if not reviews: await callback.answer("Отзывов нет.", show_alert=True); return
    lines = [f"{pe('star')} <b>Отзывы: {product.name if product else ''}</b>\n"]
    for r in reviews:
        lines.append("⭐"*r.rating + (f"\n<i>{r.text}</i>" if r.text else ""))
    await callback.message.answer("\n\n".join(lines), parse_mode="HTML")
    await callback.answer()

# ── СКИДКА ────────────────────────────────────────────────────────────────────
async def spin_discount_action(user_id, username, msg_obj, bot):
    import asyncio
    async with AsyncSessionLocal() as s:
        existing = await get_active_discount(s, user_id)
        if existing:
            h = int((existing.expires_at - datetime.utcnow()).total_seconds() // 3600)
            await msg_obj.answer(
                f"{pe('star')} Скидка <b>{existing.percent}%</b> активна ещё {h}ч.",
                parse_mode="HTML"
            ); return

    percent = random.randint(1, 10)
    msg = await msg_obj.answer("🎰 | ❓ ❓ ❓ |")
    await asyncio.sleep(0.6)
    await msg.edit_text("🎰 | 1% ❓ ❓ |")
    await asyncio.sleep(0.6)
    await msg.edit_text("🎰 | 1% 5% ❓ |")
    await asyncio.sleep(0.8)
    await msg.edit_text(f"🎰 | 1% 5% {percent}% |")
    await asyncio.sleep(0.8)

    async with AsyncSessionLocal() as s:
        expires = datetime.utcnow() + timedelta(hours=24)
        old = (await s.execute(
            select(UserDiscount).where(UserDiscount.user_id == user_id)
        )).scalar_one_or_none()
        if old:
            old.percent = percent; old.expires_at = expires; old.created_at = datetime.utcnow()
        else:
            s.add(UserDiscount(user_id=user_id, percent=percent, expires_at=expires))
        await s.commit()

    await msg.edit_text(
        f"{pe('star')} Тебе выпала скидка <b>{percent}%</b> на 24 часа!\n"
        f"{pe('check')} Применяется автоматически при покупке.",
        parse_mode="HTML"
    )
    from services.log_service import log_discount
    await log_discount(bot, user_id, username, percent)

# ── ЗАМЕНА ────────────────────────────────────────────────────────────────────
@router.message(ReplaceRequestStates.log_time)
async def replace_log(message: Message, state: FSMContext):
    await state.update_data(log_info=message.text, photos=[])
    await message.answer("Отправь фото (до 5 шт.), затем напиши <b>готово</b> или «—».", parse_mode="HTML")
    await state.set_state(ReplaceRequestStates.photos)

@router.message(ReplaceRequestStates.photos, F.photo)
async def replace_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    if len(photos) >= 5: await message.answer("Максимум 5."); return
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(f"Фото {len(photos)}/5.")

@router.message(ReplaceRequestStates.photos, F.text)
async def replace_photos_done(message: Message, state: FSMContext):
    if message.text.strip().lower() in ("готово", "—", "-"):
        await message.answer("Опиши жалобу:"); await state.set_state(ReplaceRequestStates.complaint)
    else:
        await message.answer("Отправь фото или напиши <b>готово</b>.", parse_mode="HTML")

@router.message(ReplaceRequestStates.complaint)
async def replace_complaint(message: Message, state: FSMContext):
    data = await state.get_data()
    async with AsyncSessionLocal() as s:
        try:
            req = await create_replace_request(s, message.from_user.id, data["log_info"],
                                               data.get("photos", []), message.text)
        except ValueError as e:
            await message.answer(f"{pe('warning')} {e}", parse_mode="HTML"); await state.clear(); return
        for admin_id in ADMIN_IDS:
            try:
                photos = data.get("photos", [])
                if photos:
                    await message.bot.send_media_group(admin_id, [InputMediaPhoto(media=p) for p in photos])
                await message.bot.send_message(
                    admin_id,
                    f"{pe('hammer')} <b>Замена #{req.id}</b>\n"
                    f"{pe('user')} @{message.from_user.username} (<code>{message.from_user.id}</code>)\n"
                    f"Лог: {data['log_info']}\nЖалоба: {message.text}",
                    parse_mode="HTML", reply_markup=replace_action_kb(req.id)
                )
            except Exception as e: print(f"notify: {e}")
    await message.answer(f"{pe('check')} Заявка отправлена.", parse_mode="HTML")
    await state.clear()

# ── РАЗБАН ────────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "unban_request")
async def unban_start(callback: CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as s:
        user = await s.get(User, callback.from_user.id)
        if not user or not user.is_banned:
            await callback.answer("Вы не заблокированы!", show_alert=True); return
    await callback.message.answer("Отправь фото доказательства или напиши «—».")
    await state.set_state(UnbanProcess.waiting_photos)
    await state.update_data(photos=[])
    await callback.answer()

@router.message(UnbanProcess.waiting_photos, F.photo)
async def unban_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(f"Фото {len(photos)}. Ещё или напиши <b>готово</b>.", parse_mode="HTML")

@router.message(UnbanProcess.waiting_photos, F.text)
async def unban_photo_text(message: Message, state: FSMContext):
    if message.text.strip().lower() in ("готово", "—", "-"):
        await message.answer("Опиши причину:"); await state.set_state(UnbanProcess.waiting_description)
    else:
        await message.answer("Отправь фото или напиши <b>готово</b>.", parse_mode="HTML")

@router.message(UnbanProcess.waiting_description)
async def unban_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Отправить заявку?", reply_markup=unban_confirm_kb())
    await state.set_state(UnbanProcess.confirm)

@router.callback_query(UnbanProcess.confirm, F.data == "unban_confirm")
async def unban_confirm_cb(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id
    async with AsyncSessionLocal() as s:
        req = UnbanRequest(user_id=user_id,
                           photos=",".join(data.get("photos", [])) or None,
                           description=data.get("description", "-"))
        s.add(req); await s.commit()
        for admin_id in ADMIN_IDS:
            try:
                photos = data.get("photos", [])
                if photos:
                    await callback.bot.send_media_group(admin_id, [InputMediaPhoto(media=p) for p in photos])
                await callback.bot.send_message(
                    admin_id,
                    f"{pe('unlock')} <b>Разблокировка #{req.id}</b>\n"
                    f"@{callback.from_user.username} (<code>{user_id}</code>)\n{data.get('description', '-')}",
                    parse_mode="HTML", reply_markup=unban_action_kb(req.id)
                )
            except Exception: pass
    await callback.message.answer(f"{pe('check')} Заявка отправлена.", parse_mode="HTML")
    await state.clear()

@router.callback_query(UnbanProcess.confirm, F.data == "unban_cancel")
async def unban_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Отменено."); await state.clear()
