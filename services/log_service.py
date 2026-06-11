from aiogram import Bot
from config import LOG_CHAT_ID, pe

async def log_purchase(bot: Bot, user_id: int, username: str, product_name: str,
                       amount: int, total_price: float, lines: list[str] = None):
    """
    Отправляет в канал лог покупки с выданными строками (номерами).
    lines — список выданных строк товара.
    """
    uname = f"@{username}" if username else f"id:{user_id}"
    header = (
        f"{pe('box')} <b>Покупка</b>\n"
        f"{pe('user')} {uname} (<code>{user_id}</code>)\n"
        f"{pe('briefcase')} Товар: <b>{product_name}</b>\n"
        f"{pe('cart')} Кол-во: {amount} шт.\n"
        f"{pe('wallet')} Итого: <b>{total_price:.2f}$</b>"
    )
    if lines:
        nums = "\n".join(f"  <code>{i+1}.</code> <code>{l}</code>" for i, l in enumerate(lines))
        header += f"\n\n{pe('books')} <b>Выданные строки:</b>\n{nums}"
    try:
        await bot.send_message(LOG_CHAT_ID, header, parse_mode="HTML")
    except Exception as e:
        print(f"Log purchase error: {e}")

async def log_register(bot: Bot, user_id: int, username: str):
    uname = f"@{username}" if username else f"id:{user_id}"
    text = (
        f"{pe('bell')} <b>Новый пользователь</b>\n"
        f"{pe('user')} {uname} (<code>{user_id}</code>)"
    )
    try:
        await bot.send_message(LOG_CHAT_ID, text, parse_mode="HTML")
    except Exception as e:
        print(f"Log register error: {e}")

async def log_refill(bot: Bot, user_id: int, username: str, amount: float):
    uname = f"@{username}" if username else f"id:{user_id}"
    text = (
        f"{pe('wallet')} <b>Пополнение</b>\n"
        f"{pe('user')} {uname} (<code>{user_id}</code>)\n"
        f"{pe('check')} +{amount:.2f}$"
    )
    try:
        await bot.send_message(LOG_CHAT_ID, text, parse_mode="HTML")
    except Exception as e:
        print(f"Log refill error: {e}")

async def log_promo(bot: Bot, user_id: int, username: str, code: str, amount: float):
    uname = f"@{username}" if username else f"id:{user_id}"
    text = (
        f"{pe('gift')} <b>Промокод</b>\n"
        f"{pe('user')} {uname} (<code>{user_id}</code>)\n"
        f"{pe('star')} Код: <code>{code}</code> → +{amount:.2f}$"
    )
    try:
        await bot.send_message(LOG_CHAT_ID, text, parse_mode="HTML")
    except Exception as e:
        print(f"Log promo error: {e}")

async def log_broadcast(bot: Bot, admin_id: int, text: str, ok: int, fail: int):
    msg = (
        f"{pe('mega')} <b>Рассылка</b>\n"
        f"{pe('dev')} Админ: <code>{admin_id}</code>\n"
        f"{pe('check')} Доставлено: {ok} | {pe('ban')} Ошибок: {fail}\n"
        f"Текст: {text[:100]}"
    )
    try:
        await bot.send_message(LOG_CHAT_ID, msg, parse_mode="HTML")
    except Exception as e:
        print(f"Log broadcast error: {e}")
