import asyncio
import os
import sys
from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
from database.database import init_db, AsyncSessionLocal
from database.models import Invoice, User
from services.payment_service import check_pending_invoices
from handlers.user_handlers import router as user_router
from handlers.admin_handlers import router as admin_router
from config import ADMIN_IDS

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8961635368:AAGrLICFaRDceOFDa5RBIlY2274_DKtvs0k")
ADMIN_IDS_STR = os.environ.get("ADMIN_IDS", "1073780833")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip()]

if not BOT_TOKEN:
    print("❌ BOT_TOKEN не задан!")
    sys.exit(1)

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
    print(f"✅ Web server started on port {port}")

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
                                try:
                                    await bot.send_message(inv.user_id, f"✅ Платёж на {inv.amount} USDT зачислен!")
                                except:
                                    pass
                        elif new_status == "expired":
                            inv.status = "expired"
                    await session.commit()
        except Exception as e:
            print(f"Payment checker error: {e}")
        await asyncio.sleep(10)

# ---------- Middleware для блокировки ----------
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

class BanMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id

        if user_id and user_id not in ADMIN_IDS:
            async with AsyncSessionLocal() as session:
                user = await session.get(User, user_id)
                if user and user.is_banned:
                    if isinstance(event, Message):
                        await event.answer(
                            f"🚫 Вы заблокированы.\nПричина: {user.ban_reason or 'не указана'}",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="Разжаловать: Да", callback_data="unban_request"),
                                 InlineKeyboardButton(text="Нет", callback_data="unban_ignore")]
                            ])
                        )
                    elif isinstance(event, CallbackQuery):
                        await event.answer("Вы заблокированы.", show_alert=True)
                    return
        return await handler(event, data)

async def main():
    print("🚀 Запуск бота...")
    await init_db()
    print("✅ База данных готова")

    import config
    config.ADMIN_IDS = ADMIN_IDS

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.update.middleware(BanMiddleware())

    dp.include_router(user_router)
    dp.include_router(admin_router)

    asyncio.create_task(start_web_server())
    asyncio.create_task(payment_checker(bot))

    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
