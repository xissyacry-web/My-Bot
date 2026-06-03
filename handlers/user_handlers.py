import html
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from datetime import datetime
from database.database import AsyncSessionLocal
from database.models import User, Invoice, Promocode, Purchase, Product, UnbanRequest
from keyboards.inline import main_menu_keyboard, categories_keyboard, products_keyboard, payment_keyboard
from services.user_service import get_user, create_user
from services.product_service import get_categories, get_products_by_category, buy_product, get_all_products_text
from services.payment_service import create_invoice
from services.replace_service import create_replace_request
from services.log_service import log_purchase, log_register, log_refill, log_promo
from utils.states import ReplenishBalance, PromocodeInput, BuyProduct, UnbanProcess, ReplaceRequestStates
from utils.emoji import tg_emoji
from config import ADMIN_IDS
from sqlalchemy import select

router = Router()

async def ensure_user(user_id: int, username: str = None):
    async with AsyncSessionLocal() as session:
        user = await get_user(session, user_id)
        if not user:
            user = await create_user(session, user_id, username)
        return user

async def clear_state(callback: CallbackQuery, state: FSMContext):
    if await state.get_state():
        await state.clear()

# ========== СТАРТ ==========
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await ensure_user(message.from_user.id, message.from_user.username)
    text = (
        f"{tg_emoji('catalog', '🛒')} Добро пожаловать в магазин!\n"
        f"Выберите действие:"
    )
    await message.answer(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")

# ========== ГЛАВНОЕ МЕНЮ ==========
@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await clear_state(callback, state)
    await callback.message.edit_text(
        f"{tg_emoji('catalog', '🛒')} Главное меню:",
        reply_markup=main_menu_keyboard(), parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "menu_catalog")
async def menu_catalog(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session, parent_id=None)
        if cats:
            await callback.message.edit_text(
                f"{tg_emoji('catalog', '🛒')} Выберите категорию:",
                reply_markup=categories_keyboard(cats), parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                f"{tg_emoji('warning', '⚠️')} Каталог пуст.",
                reply_markup=main_menu_keyboard(), parse_mode="HTML"
            )
    await callback.answer()

@router.callback_query(F.data == "menu_profile")
async def menu_profile(callback: CallbackQuery):
    user = await ensure_user(callback.from_user.id, callback.from_user.username)
    days = (datetime.utcnow() - user.registered_at).days
    text = (
        f"{tg_emoji('profile', '👤')} Профиль\n"
        f"ID: {user.user_id}\n"
        f"Username: @{html.escape(user.username or 'нет')}\n"
        f"Баланс: {user.balance:.2f}$\n"
        f"Регистрация: {user.registered_at.strftime('%d.%m.%Y')} ({days} дн.)"
    )
    await callback.message.edit_text(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "menu_stock")
async def menu_stock(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        stock_text = await get_all_products_text(session)
    await callback.message.edit_text(
        f"{tg_emoji('stock', '📦')} Наличие товаров:\n\n{stock_text}",
        reply_markup=main_menu_keyboard(), parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "menu_topup")
async def menu_topup(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        f"{tg_emoji('topup', '✅')} Введите сумму пополнения в $:",
        parse_mode="HTML"
    )
    await state.set_state(ReplenishBalance.amount)
    await callback.answer()

@router.callback_query(F.data == "menu_promo")
async def menu_promo(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        f"{tg_emoji('promo', '🎁')} Введите промокод:",
        parse_mode="HTML"
    )
    await state.set_state(PromocodeInput.code)
    await callback.answer()

@router.callback_query(F.data == "menu_history")
async def menu_history(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with AsyncSessionLocal() as session:
        purchases = (await session.execute(
            select(Purchase).where(Purchase.user_id == user_id)
            .order_by(Purchase.purchased_at.desc()).limit(10)
        )).scalars().all()
        if not purchases:
            await callback.message.edit_text(
                f"{tg_emoji('history', '📁')} Покупок пока нет.",
                reply_markup=main_menu_keyboard(), parse_mode="HTML"
            )
            return
        text = f"{tg_emoji('history', '📁')} Последние покупки:\n\n"
        for p in purchases:
            product = await session.get(Product, p.product_id)
            pname = html.escape(product.name) if product else "удалённый товар"
            text += (
                f"{tg_emoji('buy', '🔗')} ID {p.id} | {pname}\n"
                f"💰 {p.price}$ x {p.amount} шт.\n"
                f"{tg_emoji('time', '🕓')} {p.purchased_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            )
        await callback.message.edit_text(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "menu_support")
async def menu_support(callback: CallbackQuery):
    await callback.message.edit_text(
        f"{tg_emoji('support', '🧑‍💻')} Свяжитесь с поддержкой: @Xissya",
        reply_markup=main_menu_keyboard(), parse_mode="HTML"
    )
    await callback.answer()

# ========== КАТАЛОГ ==========
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
            await callback.message.edit_text(
                f"{tg_emoji('catalog', '🛒')} Выберите подкатегорию:",
                reply_markup=categories_keyboard(subcats), parse_mode="HTML"
            )
        else:
            products = await get_products_by_category(session, cat_id)
            if products:
                text = f"{tg_emoji('catalog', '🛒')} Доступные товары:\n\n"
                for p in products:
                    qty = "∞" if p.quantity == 0 else str(p.quantity)
                    desc = html.escape(p.description) if p.description else "без описания"
                    text += (
                        f"{tg_emoji('star', '⭐')} {html.escape(p.name)}\n"
                        f"💰 Цена: {p.price}$ за шт.\n"
                        f"{tg_emoji('stock', '📦')} В наличии: {qty} шт.\n"
                        f"📝 {desc}\n\n"
                    )
                await callback.message.edit_text(text, reply_markup=products_keyboard(products), parse_mode="HTML")
            else:
                await callback.answer("В этой категории пока нет товаров", show_alert=True)
    await callback.answer()

@router.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        cats = await get_categories(session, parent_id=None)
        if cats:
            await callback.message.edit_text(
                f"{tg_emoji('catalog', '🛒')} Категории:",
                reply_markup=categories_keyboard(cats), parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                f"{tg_emoji('warning', '⚠️')} Каталог пуст.",
                reply_markup=main_menu_keyboard(), parse_mode="HTML"
            )
    await callback.answer()

# ========== ПОКУПКА ==========
@router.callback_query(F.data.startswith("buy_"))
async def buy_start(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[1])
    async with AsyncSessionLocal() as session:
        product = await session.get(Product, product_id)
        if not product or not product.is_available:
            await callback.answer("Товар недоступен", show_alert=True)
            return
        qty = "∞" if product.quantity == 0 else str(product.quantity)
        text = (
            f"{tg_emoji('buy', '🔗')} {html.escape(product.name)}\n"
            f"💰 Цена: {product.price}$ за шт.\n"
            f"📝 {html.escape(product.description or 'Описание отсутствует')}\n\n"
            f"Введите количество (доступно {qty} шт.):"
        )
        await callback.message.answer(text, parse_mode="HTML")
        await state.set_state(BuyProduct.amount)
        await state.update_data(product_id=product_id)
    await callback.answer()

@router.message(BuyProduct.amount)
async def buy_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount <= 0: raise ValueError
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
            qleft = result.get('quantity_left', 0)
            qleft_str = f"{qleft} шт." if isinstance(qleft, int) and qleft > 0 else ("∞" if qleft == 0 else qleft)
            text = (
                f"{tg_emoji('topup', '✅')} Куплено {amount} шт.\n"
                f"Товар: {result['product_name']}\n"
                f"Остаток: {result['balance']:.2f}$\n"
                f"Осталось товара: {qleft_str}"
            )
            await message.answer(text, parse_mode="HTML")
            if result.get("content"):
                await message.answer(
                    f"{tg_emoji('buy', '🔗')} Ваш товар:\n{html.escape(result['content'])}",
                    parse_mode="HTML"
                )
            if result.get("file_id"):
                try: await message.answer_document(result["file_id"])
                except: pass
            await log_purchase(message.bot, user_id, message.from_user.username, result['product_name'], amount, result.get('price', 0))
        else:
            await message.answer(f"❌ {result['error']}")
    await state.clear()

# ========== ПОПОЛНЕНИЕ ==========
@router.message(ReplenishBalance.amount)
async def process_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0: raise ValueError
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
        session.add(Invoice(user_id=message.from_user.id, invoice_id=inv['invoice_id'], amount=amount))
        await session.commit()
    await message.answer(
        f"{tg_emoji('topup', '✅')} Счёт на {amount}$ создан.\nОплатите и нажмите «Проверить оплату».",
        reply_markup=payment_keyboard(inv['pay_url']), parse_mode="HTML"
    )
    await state.clear()

@router.callback_query(F.data == "check_payment")
async def check_payment(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with AsyncSessionLocal() as session:
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
            await callback.message.answer(
                f"{tg_emoji('topup', '✅')} Зачислено {inv.amount:.2f}$",
                parse_mode="HTML"
            )
            await log_refill(callback.bot, user_id, callback.from_user.username, inv.amount)
        elif data and data['status'] == 'expired':
            inv.status = 'expired'
            await session.commit()
            await callback.message.answer("⌛ Счёт истёк.")
        else:
            await callback.answer("Оплата не поступила.", show_alert=True)
    await callback.answer()

# ========== ПРОМОКОД ==========
@router.message(PromocodeInput.code)
async def promocode_apply(message: Message, state: FSMContext):
    code = message.text.strip()
    user_id = message.from_user.id
    async with AsyncSessionLocal() as session:
        user = await get_user(session, user_id)
        if not user:
            await message.answer("Сначала /start")
            await state.clear()
            return
        promo = await session.get(Promocode, code)
        used = [c.strip() for c in user.used_promocodes.split(',') if c.strip()]
        if code in used:
            await message.answer(f"{tg_emoji('ban', '🚫')} Уже использован.", parse_mode="HTML")
            await state.clear()
            return
        if not promo or not promo.is_active:
            await message.answer(f"{tg_emoji('ban', '🚫')} Недействителен.", parse_mode="HTML")
        elif promo.expires_at and promo.expires_at < datetime.utcnow():
            await message.answer(f"{tg_emoji('time', '🕓')} Истёк.", parse_mode="HTML")
        elif promo.max_activations is not None and promo.used_count >= promo.max_activations:
            await message.answer(f"{tg_emoji('ban', '🚫')} Лимит исчерпан.", parse_mode="HTML")
        else:
            user.balance += promo.bonus_amount
            promo.used_count += 1
            used.append(code)
            user.used_promocodes = ','.join(used)
            await session.commit()
            await message.answer(
                f"{tg_emoji('promo', '🎁')} Промокод активирован! +{promo.bonus_amount:.2f}$",
                parse_mode="HTML"
            )
            await log_promo(message.bot, user_id, message.from_user.username, code, promo.bonus_amount)
    await state.clear()

# ========== ЗАМЕНА ==========
@router.callback_query(F.data == "menu_replace")
async def menu_replace(callback: CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as session:
        exists = (await session.execute(
            select(Purchase).where(Purchase.user_id == callback.from_user.id, Purchase.status == 'completed')
        )).first()
        if not exists:
            await callback.answer("Нет завершённых покупок.", show_alert=True)
            return
    await callback.message.answer(
        f"{tg_emoji('replace', '⚠️')} Введите номер лога и время покупки (одним сообщением):",
        parse_mode="HTML"
    )
    await state.set_state(ReplaceRequestStates.log_time)
    await callback.answer()

@router.message(ReplaceRequestStates.log_time)
async def replace_log_time(message: Message, state: FSMContext):
    await state.update_data(log_info=message.text)
    await message.answer(
        f"{tg_emoji('replace', '⚠️')} Отправьте фото (до 5). Когда закончите, напишите 'готово'.",
        parse_mode="HTML"
    )
    await state.set_state(ReplaceRequestStates.photos)
    await state.update_data(photos=[])

@router.message(ReplaceRequestStates.photos, F.photo)
async def replace_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get('photos', [])
    if len(photos) >= 5:
        await message.answer(
            f"{tg_emoji('warning', '⚠️')} Максимум 5 фото. Напишите 'готово'.",
            parse_mode="HTML"
        )
        return
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(
        f"{tg_emoji('star', '⭐')} Фото {len(photos)} получено. Отправьте ещё или напишите 'готово'.",
        parse_mode="HTML"
    )

@router.message(ReplaceRequestStates.photos, F.text)
async def replace_photos_done(message: Message, state: FSMContext):
    if message.text.strip().lower() != "готово":
        await message.answer(
            f"{tg_emoji('replace', '⚠️')} Отправьте фото или напишите 'готово'.",
            parse_mode="HTML"
        )
        return
    data = await state.get_data()
    photos = data.get('photos', [])
    log_info = data['log_info']
    async with AsyncSessionLocal() as session:
        try:
            req = await create_replace_request(session, message.from_user.id, log_info, photos)
        except ValueError as e:
            await message.answer(f"❌ {e}")
            await state.clear()
            return
        for admin_id in ADMIN_IDS:
            try:
                caption = (
                    f"{tg_emoji('replace', '⚠️')} Заявка на замену #{req.id}\n"
                    f"👤 @{html.escape(message.from_user.username or '')} ({message.from_user.id})\n"
                    f"Лог/время: {html.escape(log_info)}"
                )
                if photos:
                    media = [InputMediaPhoto(media=pid) for pid in photos]
                    await message.bot.send_media_group(admin_id, media)
                await message.bot.send_message(admin_id, caption, parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"replace_approve_{req.id}"),
                         InlineKeyboardButton(text="❌ Отказать", callback_data=f"replace_reject_{req.id}")]
                    ]))
            except Exception as e:
                print(f"Ошибка уведомления админа: {e}")
    await message.answer(
        f"{tg_emoji('topup', '✅')} Заявка отправлена. Ожидайте решения.",
        parse_mode="HTML"
    )
    await state.clear()

# ========== РАЗЖАЛОВАНИЕ ==========
@router.callback_query(F.data == "unban_request")
async def unban_request(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if not user or not user.is_banned:
            await callback.answer("Вы не заблокированы!", show_alert=True)
            return
    await callback.message.answer("Начинаем процесс разжалования.\nОтправьте фото (по одному). Если фото нет, напишите '-'")
    await state.set_state(UnbanProcess.waiting_photos)
    await state.update_data(photos=[])
    await callback.answer()

@router.message(UnbanProcess.waiting_photos, F.photo)
async def unban_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get('photos', [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(f"Фото {len(photos)} получено. Отправьте ещё или напишите 'готово'.")

@router.message(UnbanProcess.waiting_photos, F.text)
async def unban_photo_text(message: Message, state: FSMContext):
    if message.text.strip().lower() == "готово":
        data = await state.get_data()
        photos = data.get('photos', [])
        if not photos:
            await message.answer("Вы не отправили ни одного фото. Отправьте фото или напишите '-' (если фото нет).")
            return
        await state.update_data(photos=photos)
        await message.answer("Сколько фото вы отправили (для проверки)? Напишите число или 'готово', если всё верно.")
        await state.set_state(UnbanProcess.waiting_done)
    elif message.text.strip() == "-":
        await state.update_data(photos=[])
        await message.answer("Фото не приложены. Теперь опишите вашу жалобу текстом:")
        await state.set_state(UnbanProcess.waiting_description)
    else:
        await message.answer("Отправьте фото или напишите 'готово'.")

@router.message(UnbanProcess.waiting_done)
async def unban_count(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get('photos', [])
    if message.text.strip().lower() == "готово":
        await message.answer(f"Принято {len(photos)} фото. Теперь опишите вашу жалобу текстом:")
        await state.set_state(UnbanProcess.waiting_description)
    else:
        try:
            count = int(message.text)
            if count != len(photos):
                await message.answer(f"Вы отправили {len(photos)} фото, а указали {count}. Отправьте ещё фото или напишите 'готово' ещё раз.")
                return
            await message.answer(f"Верно, {count} фото. Теперь опишите вашу жалобу текстом:")
            await state.set_state(UnbanProcess.waiting_description)
        except:
            await message.answer("Введите число или 'готово'.")

@router.message(UnbanProcess.waiting_description)
async def unban_description(message: Message, state: FSMContext):
    description = message.text
    await state.update_data(description=description)
    await message.answer("Проверьте ваши данные. Отправить разжалование?",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="Отправить", callback_data="unban_confirm"),
                              InlineKeyboardButton(text="Отмена", callback_data="unban_cancel")]
                         ]))
    await state.set_state(UnbanProcess.confirm)

@router.callback_query(UnbanProcess.confirm, F.data == "unban_confirm")
async def unban_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    photos = data.get('photos', [])
    description = data.get('description', '-')
    user_id = callback.from_user.id

    async with AsyncSessionLocal() as session:
        req = UnbanRequest(
            user_id=user_id,
            photos=','.join(photos) if photos else None,
            description=description
        )
        session.add(req)
        await session.commit()
        for admin_id in ADMIN_IDS:
            try:
                if photos:
                    media = [InputMediaPhoto(media=pid) for pid in photos]
                    await callback.bot.send_media_group(admin_id, media)
                await callback.bot.send_message(admin_id,
                    f"🔓 Заявка на разжалование #{req.id}\n"
                    f"Пользователь: @{callback.from_user.username} ({user_id})\n"
                    f"Жалоба: {description}",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"unban_approve_{req.id}"),
                         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"unban_reject_{req.id}")]
                    ]))
            except Exception as e:
                print(f"Ошибка уведомления админа: {e}")
    await callback.message.answer("Заявка на разжалование отправлена администратору.")
    await state.clear()

@router.callback_query(UnbanProcess.confirm, F.data == "unban_cancel")
async def unban_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Разжалование отменено.")
    await state.clear()

@router.callback_query(F.data == "unban_ignore")
async def unban_ignore(callback: CallbackQuery):
    await callback.answer("Ок")
