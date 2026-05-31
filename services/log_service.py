from config import LOG_CHAT_ID
from aiogram import Bot

async def log_to_channel(bot: Bot, text: str):
    if LOG_CHAT_ID:
        try: await bot.send_message(LOG_CHAT_ID, text)
        except: pass

async def log_purchase(bot, user_id, username, product_name, amount, price):
    text = f"🛒 Покупка\n👤 @{username or '—'} ({user_id})\n📦 {product_name} × {amount}\n💵 {price:.2f}$"
    await log_to_channel(bot, text)

async def log_refill(bot, user_id, username, amount):
    text = f"💰 Пополнение\n👤 @{username or '—'} ({user_id})\n💵 +{amount:.2f}$"
    await log_to_channel(bot, text)

async def log_promo(bot, user_id, username, code, bonus):
    text = f"🎁 Промокод\n👤 @{username or '—'} ({user_id})\n🏷 {code} → +{bonus:.2f}$"
    await log_to_channel(bot, text)

async def log_register(bot, user_id, username):
    text = f"🆕 Новый пользователь: @{username or '—'} ({user_id})"
    await log_to_channel(bot, text)

async def log_broadcast(bot, admin_id, text, success, fail):
    msg = f"📨 Рассылка от {admin_id}\n✅ {success} | ❌ {fail}\n\n{text[:100]}..."
    await log_to_channel(bot, msg)
