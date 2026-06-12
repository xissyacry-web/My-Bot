import asyncio, os
from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
from database.database import init_db, AsyncSessionLocal
from database.models import Invoice, User, ScheduledBroadcast
from services.payment_service import get_invoice
from handlers.user_handlers import router as user_router
from handlers.admin_handlers import router as admin_router
from config import ADMIN_IDS, BOT_TOKEN
from sqlalchemy import select
from datetime import datetime

async def handle(request):
    return web.Response(text="OK")

async def start_web():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8000))).start()

async def payment_checker(bot: Bot):
    while True:
        try:
            async with AsyncSessionLocal() as s:
                invs = (await s.execute(select(Invoice).where(Invoice.status == 'active'))).scalars().all()
                for inv in invs:
                    data = await get_invoice(inv.invoice_id)
                    if data and data['status'] == 'paid':
                        inv.status = 'paid'
                        user = await s.get(User, inv.user_id)
                        if user:
                            user.balance += inv.amount
                            try: await bot.send_message(inv.user_id, f"✅ Зачислено {inv.amount:.2f}$ ({inv.asset})")
                            except Exception: pass
                    elif data and data['status'] == 'expired':
                        inv.status = 'expired'
                await s.commit()
        except Exception as e:
            print(f"Payment checker: {e}")
        await asyncio.sleep(15)

async def scheduled_broadcasts(bot: Bot):
    while True:
        try:
            async with AsyncSessionLocal() as s:
                now = datetime.utcnow()
                pending = (await s.execute(
                    select(ScheduledBroadcast).where(ScheduledBroadcast.sent == False, ScheduledBroadcast.send_at <= now)
                )).scalars().all()
                for br in pending:
                    users = (await s.execute(select(User.user_id))).scalars().all()
                    ok = fail = 0
                    for uid in users:
                        try: await bot.send_message(uid, br.text); ok += 1
                        except Exception: fail += 1
                    br.sent = True
                    for admin_id in ADMIN_IDS:
                        try: await bot.send_message(admin_id, f"📨 Запланированная рассылка отправлена. ✅{ok} ❌{fail}")
                        except Exception: pass
                await s.commit()
        except Exception as e:
            print(f"Scheduler: {e}")
        await asyncio.sleep(30)

from aiogram import BaseMiddleware

class BanMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        uid = getattr(getattr(event, 'from_user', None), 'user_id', None) or \
              getattr(getattr(event, 'from_user', None), 'id', None)
        if uid and uid not in ADMIN_IDS:
            async with AsyncSessionLocal() as s:
                user = await s.get(User, uid)
                if user and user.is_banned:
                    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Разжаловать", callback_data="unban_request")]])
                    if isinstance(event, Message):
                        await event.answer(f"🚫 Вы заблокированы.\nПричина: {user.ban_reason or '—'}", reply_markup=kb)
                    elif isinstance(event, CallbackQuery):
                        await event.answer("Вы заблокированы.", show_alert=True)
                    return
        return await handler(event, data)

async def main():
    await init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.update.middleware(BanMiddleware())
    dp.include_router(user_router)
    dp.include_router(admin_router)
    asyncio.create_task(start_web())
    asyncio.create_task(payment_checker(bot))
    asyncio.create_task(scheduled_broadcasts(bot))
    print(f"Bot started.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
