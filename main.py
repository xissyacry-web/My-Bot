import asyncio
import os
from aiogram import Bot, Dispatcher
from aiohttp import web
from database.database import init_db, AsyncSessionLocal
from database.models import Invoice, User
from services.payment_service import check_pending_invoices
from handlers.user_handlers import router as user_router
from handlers.admin_handlers import router as admin_router
from config import BOT_TOKEN, ADMIN_IDS  # Оставляем, но токены будем передавать через переменные окружения

# ---------- HTTP-сервер для поддержания активности ----------
async def handle(request):
    return web.Response(text="Bot is running")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")

# ---------- Фоновая проверка платежей ----------
async def payment_checker(bot: Bot):
    while True:
        try:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Invoice).where(Invoice.status == 'active')
                )
                active_invoices = result.scalars().all()
                if active_invoices:
                    invoice_ids = [inv.invoice_id for inv in active_invoices]
                    statuses = await check_pending_invoices(invoice_ids)
                    for inv in active_invoices:
                        new_status = statuses.get(inv.invoice_id)
                        if new_status == "paid":
                            inv.status = "paid"
                            user = await session.get(User, inv.user_id)
                            if user:
                                user.balance += inv.amount
                                await bot.send_message(
                                    inv.user_id,
                                    f"✅ Ваш платёж на {inv.amount} USDT поступил! Баланс обновлён."
                                )
                        elif new_status == "expired":
                            inv.status = "expired"
                    await session.commit()
        except Exception as e:
            print(f"Payment checker error: {e}")
        await asyncio.sleep(10)

async def main():
    # Инициализация БД
    await init_db()

    # Токены берём из переменных окружения (Render их передаст)
    bot_token = os.environ.get("BOT_TOKEN", BOT_TOKEN)
    admin_ids = os.environ.get("ADMIN_IDS", ",".join(map(str, ADMIN_IDS)))
    # Если нужно динамически обновить ADMIN_IDS из строки, можно здесь распарсить
    import config
    config.BOT_TOKEN = bot_token
    config.ADMIN_IDS = [int(x) for x in admin_ids.split(",") if x]

    bot = Bot(token=bot_token)
    dp = Dispatcher()
    dp.include_router(user_router)
    dp.include_router(admin_router)

    # Запускаем веб-сервер и фоновую проверку параллельно
    asyncio.create_task(start_web_server())
    asyncio.create_task(payment_checker(bot))

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())