from aiogram import Bot
from config import LOG_CHAT_ID, pe, pe_coin

async def _send(bot: Bot, text: str):
    try:
        await bot.send_message(LOG_CHAT_ID, text, parse_mode="HTML")
    except Exception as e:
        print(f"Log error: {e}")

async def log_purchase(bot, user_id, username, product_name, amount,
                       total_price, cashback=0.0, lines=None):
    uname = f"@{username}" if username else f"id:{user_id}"
    cb_part = f"  {pe('star')} кэшбек +{cashback:.4f}$" if cashback else ""
    text = (
        f"{pe('box')} <b>Покупка</b>\n"
        f"{pe('user')} {uname} (<code>{user_id}</code>)\n"
        f"{pe('briefcase')} <b>{product_name}</b> × {amount}\n"
        f"{pe('wallet')} {total_price:.2f}${cb_part}"
    )
    if lines:
        nums = "\n".join(
            f"  {pe('n' + str(min(i, 9)))} <code>{l}</code>"
            for i, l in enumerate(lines)
        )
        text += f"\n\n{pe('books')} <b>Выдано:</b>\n{nums}"
    await _send(bot, text)

async def log_register(bot, user_id, username, ref_by=None):
    if not bot:
        return
    uname = f"@{username}" if username else f"id:{user_id}"
    text = (
        f"{pe('bell')} <b>Новый пользователь</b>\n"
        f"{pe('user')} {uname} (<code>{user_id}</code>)"
    )
    if ref_by:
        text += f"\n{pe('link')} реферал от <code>{ref_by}</code>"
    await _send(bot, text)

async def log_refill(bot, user_id, username, amount, asset="USDT"):
    uname = f"@{username}" if username else f"id:{user_id}"
    await _send(bot,
        f"{pe('wallet')} <b>Пополнение</b>\n"
        f"{pe('user')} {uname} (<code>{user_id}</code>)\n"
        f"{pe_coin(asset)} +{amount:.2f}$ ({asset})"
    )

async def log_promo(bot, user_id, username, code, amount):
    uname = f"@{username}" if username else f"id:{user_id}"
    await _send(bot,
        f"{pe('gift')} <b>Промокод</b>\n"
        f"{pe('user')} {uname} (<code>{user_id}</code>)\n"
        f"{pe('star')} <code>{code}</code> → +{amount:.2f}$"
    )

async def log_broadcast(bot, admin_id, text, ok, fail):
    await _send(bot,
        f"{pe('mega')} <b>Рассылка</b>\n"
        f"{pe('dev')} Админ <code>{admin_id}</code>\n"
        f"{pe('check')} {ok} доставлено  {pe('ban')} {fail} ошибок\n"
        f"<i>{text[:80]}</i>"
    )

async def log_review(bot, user_id, username, product_name, rating, text_review):
    uname = f"@{username}" if username else f"id:{user_id}"
    stars = "⭐" * rating
    await _send(bot,
        f"{pe('star')} <b>Отзыв</b> {stars}\n"
        f"{pe('user')} {uname} (<code>{user_id}</code>)\n"
        f"{pe('briefcase')} {product_name}\n"
        + (f"<i>{text_review[:200]}</i>" if text_review else "")
    )

async def log_discount(bot, user_id, username, percent):
    uname = f"@{username}" if username else f"id:{user_id}"
    await _send(bot,
        f"{pe('star')} <b>Скидка</b>\n"
        f"{pe('user')} {uname} (<code>{user_id}</code>)\n"
        f"{pe('check')} {percent}% на 24 часа"
    )
