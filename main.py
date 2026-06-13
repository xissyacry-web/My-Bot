import asyncio, os, json, base64, sqlite3, tempfile
from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
from database.database import init_db, AsyncSessionLocal
from database.models import Invoice, User, ScheduledBroadcast
from services.payment_service import get_invoice
from handlers.user_handlers import router as user_router
from handlers.admin_handlers import router as admin_router
from config import ADMIN_IDS, BOT_TOKEN, pe
from sqlalchemy import select
from datetime import datetime
from keyboards.inline import banned_kb

# ── WEB SERVER ────────────────────────────────────────────────────────────────
async def handle_root(request):
    return web.Response(text="Bot is running ✅")

async def handle_import(request):
    """
    Импорт БД через веб — POST /import?token=ADMIN_TOKEN
    Body: multipart/form-data с полем 'db' (файл bot.db)
    или JSON: {"db_base64": "...base64..."}
    """
    token = request.rel_url.query.get("token", "")
    if token != os.environ.get("IMPORT_TOKEN", "secret123"):
        return web.Response(status=403, text="Forbidden")
    try:
        content_type = request.content_type or ""
        if "multipart" in content_type:
            data = await request.post()
            field = data.get("db")
            if not field:
                return web.Response(status=400, text="No 'db' field")
            db_bytes = field.file.read()
        else:
            body = await request.json()
            db_bytes = base64.b64decode(body.get("db_base64", ""))

        # Проверяем валидность SQLite
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            tmp.write(db_bytes)
            tmp_path = tmp.name
        conn = sqlite3.connect(tmp_path)
        conn.execute("SELECT 1 FROM users LIMIT 1")
        conn.close()

        import shutil
        if os.path.exists("bot.db"):
            shutil.copy2("bot.db", "bot_backup.db")
        shutil.move(tmp_path, "bot.db")

        return web.Response(text="✅ Импортировано! Перезапусти бота через Render Dashboard.")
    except Exception as e:
        return web.Response(status=500, text=f"Ошибка: {e}")

async def handle_export(request):
    """Экспорт БД через веб — GET /export?token=ADMIN_TOKEN"""
    token = request.rel_url.query.get("token", "")
    if token != os.environ.get("IMPORT_TOKEN", "secret123"):
        return web.Response(status=403, text="Forbidden")
    if not os.path.exists("bot.db"):
        return web.Response(status=404, text="bot.db not found")
    return web.FileResponse("bot.db", headers={
        "Content-Disposition": "attachment; filename=bot.db"
    })

async def start_web():
    app = web.Application(client_max_size=50 * 1024 * 1024)  # 50MB
    app.router.add_get("/", handle_root)
    app.router.add_post("/import", handle_import)
    app.router.add_get("/export", handle_export)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8000))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    print(f"Web server on port {port}")

# ── PAYMENT CHECKER ───────────────────────────────────────────────────────────
async def payment_checker(bot: Bot):
    while True:
        try:
            async with AsyncSessionLocal() as s:
                invs = (await s.execute(select(Invoice).where(Invoice.status == "active"))).scalars().all()
                for inv in invs:
                    data = await get_invoice(inv.invoice_id)
                    if data and data["status"] == "paid":
                        inv.status = "paid"
                        user = await s.get(User, inv.user_id)
                        if user:
                            user.balance += inv.amount
                            try:
                                await bot.send_message(
                                    inv.user_id,
                                    f"{pe('check')} Зачислено <b>{inv.amount:.2f}$</b> ({inv.asset})",
                                    parse_mode="HTML"
                                )
                            except Exception: pass
                    elif data and data["status"] == "expired":
                        inv.status = "expired"
                await s.commit()
        except Exception as e:
            print(f"Payment checker: {e}")
        await asyncio.sleep(15)

# ── SCHEDULER ─────────────────────────────────────────────────────────────────
async def scheduled_broadcasts(bot: Bot):
    while True:
        try:
            async with AsyncSessionLocal() as s:
                now = datetime.utcnow()
                pending = (await s.execute(
                    select(ScheduledBroadcast).where(
                        ScheduledBroadcast.sent == False,
                        ScheduledBroadcast.send_at <= now
                    )
                )).scalars().all()
                for br in pending:
                    users = (await s.execute(select(User.user_id))).scalars().all()
                    ok = fail = 0
                    for uid in users:
                        try: await bot.send_message(uid, br.text, parse_mode="HTML"); ok += 1
                        except Exception: fail += 1
                    br.sent = True
                    for admin_id in ADMIN_IDS:
                        try:
                            await bot.send_message(
                                admin_id,
                                f"{pe('mega')} Рассылка отправлена. ✅{ok} ❌{fail}",
                                parse_mode="HTML"
                            )
                        except Exception: pass
                await s.commit()
        except Exception as e:
            print(f"Scheduler: {e}")
        await asyncio.sleep(30)

# ── BAN MIDDLEWARE ────────────────────────────────────────────────────────────
from aiogram import BaseMiddleware

class BanMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        uid = None
        if hasattr(event, "from_user") and event.from_user:
            uid = event.from_user.id
        if uid and uid not in ADMIN_IDS:
            async with AsyncSessionLocal() as s:
                user = await s.get(User, uid)
                if user and user.is_banned:
                    reason = user.ban_reason or "не указана"
                    text = (
                        f"{pe('ban')} <b>Вы заблокированы</b>\n\n"
                        f"Причина: {reason}\n\n"
                        f"Вы можете подать апелляцию на разблокировку."
                    )
                    if isinstance(event, Message):
                        await event.answer(text, parse_mode="HTML", reply_markup=banned_kb())
                    elif isinstance(event, CallbackQuery):
                        await event.answer("🚫 Вы заблокированы. Нажмите кнопку для апелляции.", show_alert=True)
                        try:
                            await event.message.answer(text, parse_mode="HTML", reply_markup=banned_kb())
                        except Exception: pass
                    return
        return await handler(event, data)

# ── MAIN ──────────────────────────────────────────────────────────────────────
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
    print("Bot v5 started.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
PYEOF
echo "ok"
