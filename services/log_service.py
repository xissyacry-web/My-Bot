from config import LOG_CHAT_ID
from aiogram import Bot

async def log_to_channel(bot: Bot, text: str):
    if LOG_CHAT_ID:
        try:
            await bot.send_message(LOG_CHAT_ID, text)
        except Exception as e:
            print(f"Ошибка отправки лога: {e}")

async def log_purchase(bot: Bot, user_id: int, username: str, product_name: str, amount: int, price: float):
    text = (f"🛒 Покупка\n"
            f"👤 @{username or '—'} ({user_id})\n"
            f"📦 {product_name} × {amount}\n"
            f"💵 {price:.2f}$")
    await log_to_channel(bot, text)

async def log_refill(bot: Bot, user_id: int, username: str, amount: float):
    text = (f"💰 Пополнение\n"
            f"👤 @{username or '—'} ({user_id})\n"
            f"💵 +{amount:.2f}$")
    await log_to_channel(bot, text)

async def log_promo(bot: Bot, user_id: int, username: str, code: str, bonus: float):
    text = (f"🎁 Промокод активирован\n"
            f"👤 @{username or '—'} ({user_id})\n"
            f"🏷 Код: {code}\n"
            f"💵 +{bonus:.2f}$")
    await log_to_channel(bot, text)

async def log_register(bot: Bot, user_id: int, username: str):
    text = f"🆕 Новый пользователь: @{username or '—'} ({user_id})"
    await log_to_channel(bot, text)

async def log_replace(bot: Bot, user_id: int, username: str, log_number: str):
    text = f"🔄 Заявка на замену\n👤 @{username or '—'} ({user_id})\n📝 Номер лога: {log_number}"
    await log_to_channel(bot, text)

async def log_broadcast(bot: Bot, admin_id: int, text: str, success: int, fail: int):
    msg = f"📨 Рассылка от админа {admin_id}\n✅ {success} | ❌ {fail}\n\n{text[:100]}..."
    await log_to_channel(bot, msg)
