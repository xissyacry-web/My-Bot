import random, asyncio
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from database.database import AsyncSessionLocal
from database.models import (
    User, Product, Purchase, Invoice, Promocode,
    UserDiscount, StockNotify, Review, UnbanRequest, ReplaceRequest
)
from services.user_service import get_or_create_user, get_user
from services.product_service import get_categories, get_products_by_category, buy_product
from services.payment_service import create_invoice, get_invoice
from services.log_service import log_register, log_topup, log_purchase, log_promo
from keyboards.kb import (
    main_reply, main_inline, to_main, captcha_kb,
    categories, products, product_view, amount_pick,
    profile, choose_asset, pay_link, history, purchase_detail, review_rating,
    appeal, unban_confirm, replace_action, unban_action, after_spin, banned_kb
)
from utils.states import (
    CaptchaState, BuyState, TopupState, PromoState, ReviewState,
    ReplaceState, UnbanState, ReplaceApprove, ReplaceReject
)
from config import ADMIN_IDS, pe, BOT_USERNAME, REF_BONUS_PCT

router = Router()

# ── УТИЛИТЫ ───────────────────────────────────────────────────────────────────
async def get_discount(session, uid):
    return (await session.execute(
        select(UserDiscount).where(
            UserDiscount.user_id == uid,
            UserDiscount.expires_at > datetime.utcnow()
        )
    )).scalar_one_or_none()

async def safe_edit(cb: CallbackQuery, text: str, kb=None, pm="HTML"):
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode=pm)
    except Exception:
        await cb.message.answer(text, reply_markup=kb, parse_mode=pm)

async def send_main(target, intro: str = None):
    text = f"{pe('crown')} <b>Главное меню</b>\n\nВыбери раздел:"
    kb = main_reply()
    if isinstance(target, Message):
        if intro:
            await target.answer(intro, parse_mode="HTML")
        await target.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.message.answer(text, parse_mode="HTML", reply_markup=kb)

def gen_captcha():
    """Генерирует простой математический пример и варианты ответов"""
    ops = [
        (lambda a, b: (f"{a}+{b}", a+b)),
        (lambda a, b: (f"{a}×{b}", a*b)),
        (lambda a, b: (f"{a}-{b}", a-b)),
    ]
    op = random.choice(ops)
    a = random.randint(1, 9)
    b = random.randint(1, 9)
    question, answer = op(a, b)
    if answer < 0:  # для вычитания делаем чтобы a >= b
        a, b = max(a, b), min(a, b)
        question, answer = f"{a}-{b}", a-b
    # Генерируем 5 вариантов — 1 правильный + 4 неверных
    options = {answer}
    while len(options) < 5:
        wrong = answer + random.randint(-5, 5)
        if wrong != answer and wrong >= 0:
            options.add(wrong)
    options = list(options)
    random.shuffle(options)
    return question, answer, options

# ── START + КАПЧА ─────────────────────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    args = message.text.split(maxsplit=1)
    ref_code = None
    if len(args) > 1 and args[1].startswith("ref_"):
        ref_code = args[1][4:]
        # Защита: нельзя использовать свою же реф-ссылку
        async with AsyncSessionLocal() as s:
            user = await get_user(s, message.from_user.id)
            if user and user.ref_code == ref_code:
                ref_code = None  # игнорируем свою ссылку

    async with AsyncSessionLocal() as s:
        user = await get_user(s, message.from_user.id)
        is_new = user is None

    if is_new:
        # Показываем капчу новому пользователю
        question, answer, options = gen_captcha()
        await state.set_state(CaptchaState.waiting)
        await state.update_data(answer=answer, ref_code=ref_code,
                                uid=message.from_user.id, username=message.from_user.username)
        await message.answer(
            f"{pe('shield')} <b>Проверка</b>\n\nРешите пример:\n\n"
            f"<b>{question} = ?</b>",
            parse_mode="HTML",
            reply_markup=captcha_kb(options)
        )
    else:
        # Обновляем username если изменился
        async with AsyncSessionLocal() as s:
            user, _ = await get_or_create_user(s, message.from_user.id, message.from_user.username)
        await send_main(message, f"{pe('crown')} С возвращением!")

@router.callback_query(CaptchaState.waiting, F.data.startswith("cap_"))
async def cb_captcha(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    chosen = int(callback.data[4:])
    correct = data["answer"]

    if chosen != correct:
        # Неверный ответ — новая капча
        question, answer, options = gen_captcha()
        await state.update_data(answer=answer)
        await callback.message.edit_text(
            f"{pe('warning')} Неверно! Попробуй ещё раз:\n\n<b>{question} = ?</b>",
            parse_mode="HTML",
            reply_markup=captcha_kb(options)
        )
        await callback.answer("❌ Неверно!", show_alert=False)
        return

    # Капча пройдена — создаём пользователя
    uid = data["uid"]
    username = data["username"]
    ref_code = data.get("ref_code")

    async with AsyncSessionLocal() as s:
        user, is_new = await get_or_create_user(s, uid, username, ref_code)
        ref_by = user.referred_by
        if is_new and ref_by:
            try:
                await callback.bot.send_message(
                    ref_by,
                    f"{pe('gift')} По вашей реферальной ссылке зарегистрировался новый пользователь!",
                    parse_mode="HTML"
                )
            except Exception: pass

    await state.clear()
    await callback.message.delete()
    await log_register(callback.bot, uid, username, ref_by if is_new else None)
    await send_main(callback.message, f"{pe('check')} Верно! Добро пожаловать!")
    await callback.answer("✅ Верно!")

# ── ГЛАВНОЕ МЕНЮ ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "m_main")
async def cb_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await send_main(callback)
    await callback.answer()

# Reply кнопки
@router.message(F.text == "Каталог")
async def msg_catalog(message: Message, state: FSMContext):
    if await state.get_state(): return
    await show_catalog(message)

@router.message(F.text == "Профиль")
async def msg_profile(message: Message, state: FSMContext):
    if await state.get_state(): return
    await show_profile(message)

@router.message(F.text == "Замена")
async def msg_replace(message: Message, state: FSMContext):
    if await state.get_state(): return
    await start_replace(message, state)

@router.message(F.text == "Поддержка")
async def msg_support(message: Message, state: FSMContext):
    if await state.get_state(): return
    await message.answer(f"{pe('info')} <b>Поддержка</b>\n\n@XissyaSup", parse_mode="HTML", reply_markup=to_main())

@router.message(F.text == "Скидка")
async def msg_discount(message: Message, state: FSMContext):
    if await state.get_state(): return
    await run_discount(message)

# Inline кнопки главного меню
@router.callback_query(F.data == "m_catalog")
async def cb_catalog(callback: CallbackQuery):
    await show_catalog(callback.message)
    await callback.answer()

@router.callback_query(F.data == "m_profile")
async def cb_profile_cb(callback: CallbackQuery):
    await show_profile(callback)
    await callback.answer()

@router.callback_query(F.data == "m_support")
async def cb_support(callback: CallbackQuery):
    await safe_edit(callback, f"{pe('info')} <b>Поддержка</b>\n\n@XissyaSup", to_main())
    await callback.answer()

@router.callback_query(F.data == "m_replace")
async def cb_replace_btn(callback: CallbackQuery, state: FSMContext):
    await start_replace(callback.message, state)
    await callback.answer()

@router.callback_query(F.data == "m_discount")
async def cb_discount(callback: CallbackQuery):
    await run_discount(callback.message)
    await callback.answer()

# ── КАТАЛОГ ───────────────────────────────────────────────────────────────────
async def show_catalog(msg_obj):
    async with AsyncSessionLocal() as s:
        cats = await get_categories(s)
    if not cats:
        await msg_obj.answer(f"{pe('box')} Каталог пуст", parse_mode="HTML", reply_markup=to_main())
        return
    await msg_obj.answer(f"{pe('folder')} <b>Каталог</b>", parse_mode="HTML", reply_markup=categories(cats))

@router.callback_query(F.data.startswith("cat_"))
async def cb_cat(callback: CallbackQuery):
    cat_id = int(callback.data[4:])
    async with AsyncSessionLocal() as s:
        from database.models import Category
        cat = await s.get(Category, cat_id)
        if not cat: await callback.answer("Не найдено", show_alert=True); return
        subcats = await get_categories(s, parent_id=cat_id)
        if subcats:
            await safe_edit(callback, f"{pe('folder')} <b>{cat.name}</b>", categories(subcats))
        else:
            prods = await get_products_by_category(s, cat_id)
            if prods:
                await safe_edit(callback, f"{pe('folder')} <b>{cat.name}</b>\n\nВыбери товар:", products(prods))
            else:
                await callback.answer("Товаров нет", show_alert=True)
    await callback.answer()

@router.callback_query(F.data == "cats_back")
async def cb_cats_back(callback: CallbackQuery):
    async with AsyncSessionLocal() as s:
        cats = await get_categories(s)
    if cats:
        await safe_edit(callback, f"{pe('folder')} <b>Каталог</b>", categories(cats))
    else:
        await safe_edit(callback, f"{pe('box')} Каталог пуст", to_main())
    await callback.answer()

@router.callback_query(F.data.startswith("prod_"))
async def cb_prod(callback: CallbackQuery):
    pid = int(callback.data[5:])
    async with AsyncSessionLocal() as s:
        p = await s.get(Product, pid)
        if not p: await callback.answer("Не найдено", show_alert=True); return
        disc = await get_discount(s, callback.from_user.id)
        qty = "∞" if p.quantity == 0 else str(p.quantity)
        avg = f"⭐ {p.rating_sum/p.rating_count:.1f} ({p.rating_count})" if p.rating_count else "нет отзывов"
        out = not p.is_available
        if disc and not out:
            final = round(p.price * (1 - disc.percent/100), 2)
            price_txt = f"💰 <s>{p.price}$</s> → <b>{final}$</b> (-{disc.percent}%)"
        else:
            price_txt = f"💰 <b>{p.price}$</b>"
        text = (
            f"{pe('box')} <b>{p.name}</b>\n\n"
            f"{p.description or 'Описание отсутствует'}\n\n"
            f"{price_txt}\n"
            f"{pe('clock')} В наличии: {'нет' if out else qty + ' шт.'}\n"
            f"{pe('star')} Рейтинг: {avg}"
        )
    await callback.message.answer(text, parse_mode="HTML", reply_markup=product_view(pid, out))
    await callback.answer()

@router.callback_query(F.data.startswith("buy_"))
async def cb_buy_start(callback: CallbackQuery, state: FSMContext):
    pid = int(callback.data[4:])
    await state.update_data(product_id=pid)
    await state.set_state(BuyState.amount)
    await callback.message.answer("Введи количество:", reply_markup=amount_pick(pid))
    await callback.answer()

@router.callback_query(F.data.startswith("qa_"))
async def cb_quick_amount(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    pid, n = int(parts[1]), int(parts[2])
    await state.clear()
    await _do_buy(pid, n, callback.from_user.id, callback.from_user.username, callback.message, callback.bot)
    await callback.answer()

@router.message(BuyState.amount)
async def msg_buy_amount(message: Message, state: FSMContext):
    try:
        n = int(message.text.strip())
        if n <= 0: raise ValueError
    except Exception:
        await message.answer("Введи целое положительное число."); return
    data = await state.get_data()
    await state.clear()
    await _do_buy(data["product_id"], n, message.from_user.id, message.from_user.username, message, message.bot)

async def _do_buy(pid, amount, uid, username, msg_obj, bot):
    async with AsyncSessionLocal() as s:
        disc = await get_discount(s, uid)
        disc_pct = disc.percent if disc else 0
        res = await buy_product(s, uid, pid, amount, disc_pct)
    if res["success"]:
        cb_line = f"\n{pe('star')} Кэшбек: +{res['cashback']:.4f}$" if res.get("cashback") else ""
        await msg_obj.answer(
            f"{pe('check')} <b>Куплено {amount} шт.</b>\n"
            f"{pe('wallet')} {res['total_price']:.2f}$  |  баланс: {res['balance']:.2f}${cb_line}",
            parse_mode="HTML", reply_markup=to_main()
        )
        if res.get("content"):
            await msg_obj.answer(
                f"{pe('books')} <b>Товар:</b>\n\n<code>{res['content']}</code>",
                parse_mode="HTML"
            )
        if res.get("file_id"):
            try: await bot.send_document(uid, res["file_id"])
            except Exception: pass
        await log_purchase(bot, uid, username, res["product_name"], amount,
                           res["total_price"], res.get("cashback", 0), res.get("selected_lines", []))
    else:
        await msg_obj.answer(
            f"{pe('warning')} {res['error']}",
            parse_mode="HTML", reply_markup=to_main()
        )

@router.callback_query(F.data.startswith("notify_"))
async def cb_notify(callback: CallbackQuery):
    pid = int(callback.data[7:])
    uid = callback.from_user.id
    async with AsyncSessionLocal() as s:
        ex = (await s.execute(
            select(StockNotify).where(StockNotify.user_id==uid, StockNotify.product_id==pid)
        )).scalar_one_or_none()
        if ex: await callback.answer("Уже подписаны!", show_alert=True); return
        s.add(StockNotify(user_id=uid, product_id=pid))
        await s.commit()
    await callback.answer("🔔 Уведомим когда появится!", show_alert=True)

@router.callback_query(F.data.startswith("revs_"))
async def cb_reviews(callback: CallbackQuery):
    pid = int(callback.data[5:])
    async with AsyncSessionLocal() as s:
        p = await s.get(Product, pid)
        revs = (await s.execute(
            select(Review).where(Review.product_id==pid).order_by(Review.created_at.desc()).limit(10)
        )).scalars().all()
    if not revs: await callback.answer("Отзывов нет.", show_alert=True); return
    lines = [f"{pe('star')} <b>Отзывы: {p.name if p else ''}</b>\n"]
    for r in revs:
        lines.append("⭐"*r.rating + (f"\n<i>{r.text}</i>" if r.text else ""))
    await callback.message.answer("\n\n".join(lines), parse_mode="HTML", reply_markup=to_main())
    await callback.answer()

# ── ПРОФИЛЬ ───────────────────────────────────────────────────────────────────
async def show_profile(target):
    uid = target.from_user.id if isinstance(target, CallbackQuery) else target.from_user.id
    async with AsyncSessionLocal() as s:
        user, _ = await get_or_create_user(s, uid, target.from_user.username)
        disc = await get_discount(s, uid)
        buys = len((await s.execute(select(Purchase).where(Purchase.user_id==uid))).scalars().all())
    days = (datetime.utcnow() - user.registered_at).days
    disc_line = ""
    if disc:
        h = int((disc.expires_at - datetime.utcnow()).total_seconds() // 3600)
        disc_line = f"\n{pe('star')} Скидка: <b>{disc.percent}%</b> (ещё {h}ч.)"
    text = (
        f"{pe('user')} <b>Профиль</b>\n\n"
        f"ID: <code>{uid}</code>\n"
        f"@{user.username or '—'}\n"
        f"{pe('wallet')} Баланс: <b>{user.balance:.2f}$</b>\n"
        f"{pe('briefcase')} Покупок: {buys}  |  Потрачено: {user.total_spent:.2f}$\n"
        f"{pe('star2')} Кэшбек: {user.cashback_pct}%\n"
        f"{pe('link')} Рефералов: {user.ref_count or 0}\n"
        f"{pe('clock')} Дней с нами: {days}"
        f"{disc_line}"
    )
    if isinstance(target, CallbackQuery):
        await safe_edit(target, text, profile())
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=profile())

@router.callback_query(F.data == "p_ref")
async def cb_ref(callback: CallbackQuery):
    async with AsyncSessionLocal() as s:
        user = await get_user(s, callback.from_user.id)
    if not user: await callback.answer(); return
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{user.ref_code}"
    await callback.message.answer(
        f"{pe('link')} <b>Реферальная ссылка</b>\n\n"
        f"<code>{link}</code>\n\n"
        f"За каждое пополнение реферала вы получаете <b>{REF_BONUS_PCT}%</b> от суммы!\n"
        f"{pe('users')} Приглашено: {user.ref_count or 0}",
        parse_mode="HTML", reply_markup=to_main()
    )
    await callback.answer()

@router.callback_query(F.data == "m_profile")
async def cb_profile2(callback: CallbackQuery):
    await show_profile(callback)
    await callback.answer()

# ── ПОПОЛНЕНИЕ ────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "p_topup")
async def cb_topup(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        f"{pe('wallet')} Выбери валюту:", parse_mode="HTML",
        reply_markup=choose_asset()
    )
    await state.set_state(TopupState.asset)
    await callback.answer()

@router.callback_query(TopupState.asset, F.data.startswith("asset_"))
async def cb_asset(callback: CallbackQuery, state: FSMContext):
    asset = callback.data[6:]
    await state.update_data(asset=asset)
    await state.set_state(TopupState.amount)
    try:
        await callback.message.edit_text(
            f"{pe('wallet')} Валюта: <b>{asset}</b>\n\nВведи сумму в $:",
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            f"{pe('wallet')} Валюта: <b>{asset}</b>\n\nВведи сумму в $:",
            parse_mode="HTML"
        )
    await callback.answer()

@router.message(TopupState.amount)
async def msg_topup_amount(message: Message, state: FSMContext):
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
        await message.answer(f"{pe('warning')} Ошибка создания счёта: {e}", parse_mode="HTML")
        await state.clear(); return
    async with AsyncSessionLocal() as s:
        from database.models import Invoice
        s.add(Invoice(
            user_id=message.from_user.id,
            invoice_id=inv["invoice_id"],
            amount=amount,
            asset=asset
        ))
        await s.commit()
    await message.answer(
        f"{pe('wallet')} Счёт на <b>{amount}$ ({asset})</b>\n\nОплати и нажми «Проверить».",
        parse_mode="HTML", reply_markup=pay_link(inv["pay_url"])
    )
    await state.clear()

@router.callback_query(F.data == "check_pay")
async def cb_check_pay(callback: CallbackQuery):
    uid = callback.from_user.id
    async with AsyncSessionLocal() as s:
        from database.models import Invoice
        inv = (await s.execute(
            select(Invoice).where(Invoice.user_id==uid, Invoice.status=="active")
            .order_by(Invoice.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        if not inv:
            await callback.answer("Нет активных счетов.", show_alert=True); return
        data = await get_invoice(inv.invoice_id)
        if data and data["status"] == "paid":
            inv.status = "paid"
            user = await s.get(User, uid)
            user.balance += inv.amount
            # Реф бонус: 10% от суммы пополнения — пригласившему
            # Защита: только если referred_by != None и пользователь реально был приглашён
            if user.referred_by and user.referred_by != uid:
                bonus = round(inv.amount * REF_BONUS_PCT / 100, 4)
                referrer = await s.get(User, user.referred_by)
                if referrer and not referrer.is_banned:
                    referrer.balance += bonus
                    try:
                        await callback.bot.send_message(
                            referrer.user_id,
                            f"{pe('gift')} <b>Реф. бонус: +{bonus:.4f}$</b>\n"
                            f"Ваш реферал пополнил баланс на {inv.amount:.2f}$",
                            parse_mode="HTML"
                        )
                    except Exception: pass
            await s.commit()
            await callback.message.answer(
                f"{pe('check')} Зачислено <b>{inv.amount:.2f}$ ({inv.asset})</b>!\n"
                f"Баланс: {user.balance:.2f}$",
                parse_mode="HTML", reply_markup=to_main()
            )
            await log_topup(callback.bot, uid, callback.from_user.username, inv.amount, inv.asset)
        elif data and data["status"] == "expired":
            inv.status = "expired"; await s.commit()
            await callback.message.answer(
                f"{pe('clock')} Счёт истёк.", parse_mode="HTML", reply_markup=to_main()
            )
        else:
            await callback.answer("Оплата ещё не поступила.", show_alert=True)
    await callback.answer()

# ── ПРОМОКОД ──────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "p_promo")
async def cb_promo(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(f"{pe('gift')} Введи промокод:", parse_mode="HTML")
    await state.set_state(PromoState.code)
    await callback.answer()

@router.message(PromoState.code)
async def msg_promo(message: Message, state: FSMContext):
    await state.clear()
    code = message.text.strip().upper()
    if not code:
        await message.answer("Промокод не может быть пустым.", reply_markup=to_main()); return
    async with AsyncSessionLocal() as s:
        user = await get_user(s, message.from_user.id)
        if not user:
            await message.answer("Сначала /start"); return
        promo = await s.get(Promocode, code)
        used = [c.strip() for c in (user.used_promocodes or "").split(",") if c.strip()]
        now = datetime.utcnow()
        if code in used:
            await message.answer(
                f"{pe('ban')} Этот промокод уже использован.", parse_mode="HTML", reply_markup=to_main()
            )
        elif not promo or not promo.is_active:
            await message.answer(
                f"{pe('ban')} Промокод не найден.", parse_mode="HTML", reply_markup=to_main()
            )
        elif promo.expires_at and promo.expires_at < now:
            await message.answer(
                f"{pe('clock')} Промокод истёк.", parse_mode="HTML", reply_markup=to_main()
            )
        elif promo.max_activations is not None and promo.used_count >= promo.max_activations:
            await message.answer(
                f"{pe('ban')} Лимит активаций исчерпан.", parse_mode="HTML", reply_markup=to_main()
            )
        else:
            user.balance += promo.bonus_amount
            promo.used_count += 1
            used.append(code)
            user.used_promocodes = ",".join(used)
            await s.commit()
            await message.answer(
                f"{pe('gift')} Промокод активирован!\n"
                f"<b>+{promo.bonus_amount:.2f}$</b> на баланс!\n"
                f"Текущий баланс: {user.balance:.2f}$",
                parse_mode="HTML", reply_markup=to_main()
            )
            await log_promo(message.bot, message.from_user.id,
                           message.from_user.username, code, promo.bonus_amount)

# ── ИСТОРИЯ ПОКУПОК ───────────────────────────────────────────────────────────
@router.callback_query(F.data == "p_history")
async def cb_history(callback: CallbackQuery):
    async with AsyncSessionLocal() as s:
        purchases = (await s.execute(
            select(Purchase).where(Purchase.user_id==callback.from_user.id)
            .order_by(Purchase.purchased_at.desc()).limit(20)
        )).scalars().all()
    if not purchases:
        await callback.answer("Покупок нет.", show_alert=True); return
    await safe_edit(callback, f"{pe('books')} <b>Покупки</b>\n\nВыбери для деталей:", history(purchases))
    await callback.answer()

@router.callback_query(F.data.startswith("ph_"))
async def cb_purchase_detail(callback: CallbackQuery):
    pid = int(callback.data[3:])
    async with AsyncSessionLocal() as s:
        p = await s.get(Purchase, pid)
        if not p: await callback.answer("Не найдено", show_alert=True); return
        prod = await s.get(Product, p.product_id)
        pname = prod.name if prod else "удалён"
        rev = (await s.execute(
            select(Review).where(Review.purchase_id==pid)
        )).scalar_one_or_none()
    cb_line = f"\n{pe('star')} Кэшбек: +{p.cashback:.4f}$" if p.cashback else ""
    await safe_edit(callback,
        f"{pe('box')} <b>{pname}</b>\n"
        f"× {p.amount} шт.  {pe('wallet')} {p.price:.2f}${cb_line}\n"
        f"{pe('clock')} {p.purchased_at.strftime('%d.%m.%Y %H:%M')}",
        purchase_detail(pid, not rev)
    )
    await callback.answer()

# ── ОТЗЫВ ─────────────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("rev_"))
async def cb_rev_start(callback: CallbackQuery, state: FSMContext):
    pid = int(callback.data[4:])
    await state.update_data(purchase_id=pid)
    await state.set_state(ReviewState.rating)
    await callback.message.answer(
        f"{pe('star')} Оцени товар:", parse_mode="HTML",
        reply_markup=review_rating(pid)
    )
    await callback.answer()

@router.callback_query(ReviewState.rating, F.data.startswith("rate_"))
async def cb_rate(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    rating = int(parts[-1])
    await state.update_data(rating=rating)
    await state.set_state(ReviewState.text)
    await callback.message.answer(f"{'⭐'*rating} Напиши отзыв (или «-» пропустить):")
    await callback.answer()

@router.message(ReviewState.text)
async def msg_review_text(message: Message, state: FSMContext):
    data = await state.get_data()
    text = None if message.text.strip() == "-" else message.text.strip()
    async with AsyncSessionLocal() as s:
        p = await s.get(Purchase, data["purchase_id"])
        if not p:
            await message.answer("Не найдено.", reply_markup=to_main())
            await state.clear(); return
        prod = await s.get(Product, p.product_id)
        s.add(Review(
            user_id=message.from_user.id,
            product_id=p.product_id,
            purchase_id=p.id,
            rating=data["rating"],
            text=text
        ))
        if prod:
            prod.rating_sum += data["rating"]
            prod.rating_count += 1
        await s.commit()
    await message.answer(
        f"{pe('check')} Отзыв сохранён! {'⭐'*data['rating']}",
        parse_mode="HTML", reply_markup=to_main()
    )
    await state.clear()

# ── СКИДКА ────────────────────────────────────────────────────────────────────
async def run_discount(msg_obj):
    uid = msg_obj.chat.id if hasattr(msg_obj, 'chat') else msg_obj.from_user.id
    async with AsyncSessionLocal() as s:
        disc = await get_discount(s, uid)
        if disc:
            h = int((disc.expires_at - datetime.utcnow()).total_seconds() // 3600)
            await msg_obj.answer(
                f"{pe('star')} Скидка <b>{disc.percent}%</b> активна ещё <b>{h} ч.</b>",
                parse_mode="HTML", reply_markup=after_spin()
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
            select(UserDiscount).where(UserDiscount.user_id==uid)
        )).scalar_one_or_none()
        if old:
            old.percent = percent; old.expires_at = expires
        else:
            s.add(UserDiscount(user_id=uid, percent=percent, expires_at=expires))
        await s.commit()

    await msg.edit_text(
        f"{pe('star')} Тебе выпала скидка <b>{percent}%</b> на 24 часа!\n"
        f"{pe('check')} Применяется автоматически при покупке.",
        parse_mode="HTML", reply_markup=after_spin()
    )

# ── ЗАМЕНА ────────────────────────────────────────────────────────────────────
async def start_replace(msg_obj, state: FSMContext):
    uid = msg_obj.chat.id if hasattr(msg_obj, 'chat') else msg_obj.from_user.id
    async with AsyncSessionLocal() as s:
        ex = (await s.execute(select(Purchase).where(Purchase.user_id==uid))).first()
    if not ex:
        await msg_obj.answer(
            f"{pe('warning')} У вас нет покупок.", parse_mode="HTML", reply_markup=to_main()
        ); return
    await msg_obj.answer(
        f"{pe('hammer')} Укажи номер лога и время покупки:", parse_mode="HTML"
    )
    await state.set_state(ReplaceState.log)

@router.message(ReplaceState.log)
async def msg_replace_log(message: Message, state: FSMContext):
    await state.update_data(log=message.text, photos=[])
    await message.answer(
        "Отправь фото (до 5 шт.), затем напиши <b>готово</b> или «—».",
        parse_mode="HTML"
    )
    await state.set_state(ReplaceState.photos)

@router.message(ReplaceState.photos, F.photo)
async def msg_replace_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    if len(photos) >= 5:
        await message.answer("Максимум 5 фото."); return
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(f"Фото {len(photos)}/5 принято.")

@router.message(ReplaceState.photos, F.text)
async def msg_replace_done(message: Message, state: FSMContext):
    t = message.text.strip().lower()
    if t in ("готово", "—", "-"):
        await message.answer("Опиши проблему:"); await state.set_state(ReplaceState.text)
    else:
        await message.answer("Отправь фото или напиши <b>готово</b>.", parse_mode="HTML")

@router.message(ReplaceState.text)
async def msg_replace_text(message: Message, state: FSMContext):
    data = await state.get_data()
    uid = message.from_user.id
    async with AsyncSessionLocal() as s:
        last = (await s.execute(
            select(Purchase).where(Purchase.user_id==uid)
            .order_by(Purchase.purchased_at.desc()).limit(1)
        )).scalar_one_or_none()
        req = ReplaceRequest(
            user_id=uid,
            purchase_id=last.id if last else None,
            log_info=data["log"],
            photos=",".join(data.get("photos", [])),
            complaint=message.text
        )
        s.add(req); await s.commit()
        req_id = req.id
    for aid in ADMIN_IDS:
        try:
            photos = data.get("photos", [])
            if photos:
                await message.bot.send_media_group(aid, [InputMediaPhoto(media=p) for p in photos])
            await message.bot.send_message(
                aid,
                f"{pe('hammer')} <b>Замена #{req_id}</b>\n"
                f"{pe('user')} @{message.from_user.username} (<code>{uid}</code>)\n"
                f"Лог: {data['log']}\nЖалоба: {message.text}",
                parse_mode="HTML", reply_markup=replace_action(req_id)
            )
        except Exception as e: print(f"replace notify: {e}")
    await message.answer(
        f"{pe('check')} Заявка #{req_id} отправлена.",
        parse_mode="HTML", reply_markup=to_main()
    )
    await state.clear()

# ── РАЗБАН ────────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "unban_start")
async def cb_unban_start(callback: CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as s:
        user = await get_user(s, callback.from_user.id)
        if not user or not user.is_banned:
            await callback.answer("Вы не заблокированы!", show_alert=True); return
    await callback.message.answer("Отправь фото доказательства или напиши «—».")
    await state.update_data(photos=[])
    await state.set_state(UnbanState.photos)
    await callback.answer()

@router.message(UnbanState.photos, F.photo)
async def msg_unban_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(f"Фото {len(photos)}. Ещё или напиши <b>готово</b>.", parse_mode="HTML")

@router.message(UnbanState.photos, F.text)
async def msg_unban_photos_done(message: Message, state: FSMContext):
    if message.text.strip().lower() in ("готово", "—", "-"):
        await message.answer("Опиши причину для разблокировки:")
        await state.set_state(UnbanState.reason)

@router.message(UnbanState.reason)
async def msg_unban_reason(message: Message, state: FSMContext):
    await state.update_data(reason=message.text)
    await message.answer("Подтверди отправку заявки:", reply_markup=unban_confirm())
    await state.set_state(UnbanState.confirm)

@router.callback_query(UnbanState.confirm, F.data == "unban_send")
async def cb_unban_send(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    uid = callback.from_user.id
    async with AsyncSessionLocal() as s:
        req = UnbanRequest(
            user_id=uid,
            photos=",".join(data.get("photos", [])) or None,
            description=data.get("reason", "-")
        )
        s.add(req); await s.commit()
        req_id = req.id
    for aid in ADMIN_IDS:
        try:
            photos = data.get("photos", [])
            if photos:
                await callback.bot.send_media_group(aid, [InputMediaPhoto(media=p) for p in photos])
            await callback.bot.send_message(
                aid,
                f"{pe('unlock')} <b>Разблокировка #{req_id}</b>\n"
                f"@{callback.from_user.username} (<code>{uid}</code>)\n"
                f"{data.get('reason', '-')}",
                parse_mode="HTML", reply_markup=unban_action(req_id)
            )
        except Exception: pass
    await callback.message.answer(
        f"{pe('check')} Заявка #{req_id} отправлена.",
        parse_mode="HTML", reply_markup=to_main()
    )
    await state.clear()
    await callback.answer()

# ── ОТВЕТЫ АДМИНА НА ЗАМЕНЫ/РАЗБАНЫ ──────────────────────────────────────────
@router.callback_query(F.data.startswith("ra_"))
async def cb_ra(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await state.update_data(req_id=int(callback.data[3:]))
    await callback.message.answer("Сообщение пользователю (одобрение):")
    await state.set_state(ReplaceApprove.msg)
    await callback.answer()

@router.message(ReplaceApprove.msg)
async def msg_ra(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    data = await state.get_data()
    async with AsyncSessionLocal() as s:
        req = await s.get(ReplaceRequest, data["req_id"])
        if req:
            req.status = "approved"; req.admin_comment = message.text
            await s.commit()
            try:
                await message.bot.send_message(
                    req.user_id,
                    f"{pe('check')} Замена #{req.id} одобрена.\n{message.text}",
                    parse_mode="HTML", reply_markup=to_main()
                )
            except Exception: pass
    await message.answer(f"{pe('check')} Одобрено.")
    await state.clear()

@router.callback_query(F.data.startswith("rr_"))
async def cb_rr(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await state.update_data(req_id=int(callback.data[3:]))
    await callback.message.answer("Причина отказа:")
    await state.set_state(ReplaceReject.reason)
    await callback.answer()

@router.message(ReplaceReject.reason)
async def msg_rr(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    data = await state.get_data()
    async with AsyncSessionLocal() as s:
        req = await s.get(ReplaceRequest, data["req_id"])
        if req:
            req.status = "rejected"; req.admin_comment = message.text
            await s.commit()
            try:
                await message.bot.send_message(
                    req.user_id,
                    f"{pe('ban')} Замена #{req.id} отклонена.\n{message.text}",
                    parse_mode="HTML", reply_markup=to_main()
                )
            except Exception: pass
    await message.answer(f"{pe('check')} Отклонено.")
    await state.clear()

@router.callback_query(F.data.startswith("ua_"))
async def cb_ua(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    rid = int(callback.data[3:])
    async with AsyncSessionLocal() as s:
        req = await s.get(UnbanRequest, rid)
        if req:
            req.status = "approved"
            user = await s.get(User, req.user_id)
            if user:
                user.is_banned = False; user.ban_reason = None
            await s.commit()
            try:
                await callback.bot.send_message(
                    req.user_id,
                    f"{pe('unlock')} Вы разблокированы! Добро пожаловать обратно.",
                    parse_mode="HTML", reply_markup=main_reply()
                )
            except Exception: pass
    await callback.message.answer(f"{pe('check')} Пользователь разблокирован.")
    await callback.answer()

@router.callback_query(F.data.startswith("ur_"))
async def cb_ur(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    rid = int(callback.data[3:])
    async with AsyncSessionLocal() as s:
        req = await s.get(UnbanRequest, rid)
        if req:
            req.status = "rejected"; await s.commit()
            try:
                await callback.bot.send_message(
                    req.user_id,
                    f"{pe('ban')} В разблокировке отказано.",
                    parse_mode="HTML", reply_markup=appeal()
                )
            except Exception: pass
    await callback.message.answer(f"{pe('check')} Отклонено.")
    await callback.answer()

# ── ЛЮБОЕ ДРУГОЕ СООБЩЕНИЕ → МЕНЮ ────────────────────────────────────────────
@router.message(F.text & ~F.text.startswith("/"))
async def unknown_msg(message: Message, state: FSMContext):
    if await state.get_state(): return
    await send_main(message)
