import asyncio, os, base64, sqlite3, tempfile, shutil
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.types import Message, CallbackQuery, BotCommand, BotCommandScopeChat
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
from database.database import init_db, AsyncSessionLocal
from database.models import Invoice, User, ScheduledBroadcast
from services.payment_service import get_invoice
from handlers.user_handlers import router as user_router
from handlers.admin_handlers import router as admin_router
from config import ADMIN_IDS, BOT_TOKEN, pe, IMPORT_TOKEN
from sqlalchemy import select
from datetime import datetime

# ── WEB SERVER ────────────────────────────────────────────────────────────────
async def handle_root(request):
    token = os.environ.get("IMPORT_TOKEN", "secret123")
    url = os.environ.get("RENDER_EXTERNAL_URL", "https://your-bot.onrender.com")
    return web.Response(text=(
        f"✅ Bot is running\n\n"
        f"📤 Экспорт: GET {url}/export?token={token}\n"
        f"📥 Импорт:  POST {url}/import?token={token}\n"
        f"   (multipart field 'db' = bot.db)"
    ))

async def handle_export(request):
    token = request.rel_url.query.get("token", "")
    if token != os.environ.get("IMPORT_TOKEN", "secret123"):
        return web.Response(status=403, text="403 Forbidden")
    if not os.path.exists("bot.db"):
        return web.Response(status=404, text="bot.db не найден")
    return web.FileResponse("bot.db", headers={
        "Content-Disposition": "attachment; filename=bot.db",
        "Content-Type": "application/octet-stream",
    })

async def handle_import(request):
    token = request.rel_url.query.get("token", "")
    if token != os.environ.get("IMPORT_TOKEN", "secret123"):
        return web.Response(status=403, text="403 Forbidden")
    try:
        content_type = request.content_type or ""
        if "multipart" in content_type:
            reader = await request.multipart()
            field = await reader.next()
            if not field:
                return web.Response(status=400, text="Нет файла")
            db_bytes = await field.read()
        elif "json" in content_type:
            body = await request.json()
            db_bytes = base64.b64decode(body.get("db_base64", ""))
        else:
            db_bytes = await request.read()
        if not db_bytes:
            return web.Response(status=400, text="Пустой файл")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            tmp.write(db_bytes)
            tmp_path = tmp.name
        try:
            conn = sqlite3.connect(tmp_path)
            conn.execute("SELECT 1 FROM users LIMIT 1")
            conn.close()
        except Exception as e:
            os.remove(tmp_path)
            return web.Response(status=400, text=f"Неверный файл БД: {e}")
        if os.path.exists("bot.db"):
            shutil.copy2("bot.db", "bot_backup.db")
        shutil.move(tmp_path, "bot.db")
        return web.Response(text="✅ Импортировано! Перезапусти сервис в Render Dashboard.")
    except Exception as e:
        return web.Response(status=500, text=f"Ошибка: {e}")

async def start_web():
    app = web.Application(client_max_size=100 * 1024 * 1024)
    app.router.add_get("/", handle_root)
    app.router.add_get("/export", handle_export)
    app.router.add_post("/import", handle_import)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8000))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    print(f"Web: http://0.0.0.0:{port}")

# ── PAYMENT CHECKER ───────────────────────────────────────────────────────────
async def payment_checker(bot: Bot):
    while True:
        try:
            async with AsyncSessionLocal() as s:
                invs = (await s.execute(
                    select(Invoice).where(Invoice.status == "active")
                )).scalars().all()
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
                                    f"{pe('check')} Зачислено <b>{inv.amount:.2f}$ ({inv.asset})</b>!",
                                    parse_mode="HTML"
                                )
                            except Exception: pass
                    elif data and data["status"] == "expired":
                        inv.status = "expired"
                await s.commit()
        except Exception as e:
            print(f"[payment_checker] {e}")
        await asyncio.sleep(15)

# ── SCHEDULER ─────────────────────────────────────────────────────────────────
async def scheduler(bot: Bot):
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
                        try:
                            await bot.send_message(uid, br.text, parse_mode="HTML")
                            ok += 1
                        except Exception:
                            fail += 1
                    br.sent = True
                    for aid in ADMIN_IDS:
                        try:
                            await bot.send_message(
                                aid,
                                f"{pe('mega')} Рассылка #{br.id} отправлена. ✅{ok} ❌{fail}",
                                parse_mode="HTML"
                            )
                        except Exception: pass
                await s.commit()
        except Exception as e:
            print(f"[scheduler] {e}")
        await asyncio.sleep(30)

# ── BAN MIDDLEWARE ────────────────────────────────────────────────────────────
class BanMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        # В aiogram 3.x event_from_user доступен через data
        from_user = data.get("event_from_user")
        if not from_user:
            return await handler(event, data)

        uid = from_user.id
        if uid in ADMIN_IDS:
            return await handler(event, data)

        async with AsyncSessionLocal() as s:
            user = await s.get(User, uid)
            if user and user.is_banned:
                from keyboards.kb import banned_kb
                reason = user.ban_reason or "не указана"
                text = (
                    f"{pe('ban')} <b>Вы заблокированы</b>\n\n"
                    f"Причина: {reason}\n\n"
                    f"Вы можете подать апелляцию на разблокировку."
                )
                kb = banned_kb()
                try:
                    if hasattr(event, "callback_query") and event.callback_query:
                        await event.callback_query.answer("🚫 Вы заблокированы", show_alert=True)
                        await event.callback_query.message.answer(text, parse_mode="HTML", reply_markup=kb)
                    elif hasattr(event, "message") and event.message:
                        await event.message.answer(text, parse_mode="HTML", reply_markup=kb)
                except Exception: pass
                return

        return await handler(event, data)

# ── SETUP COMMANDS ────────────────────────────────────────────────────────────
async def setup_commands(bot: Bot):
    """Команды в меню бота (кнопка слева от поля ввода)"""
    user_commands = [
        BotCommand(command="start", description="🏠 Главное меню"),
    ]
    await bot.set_my_commands(user_commands)

    # Отдельные команды для каждого админа
    admin_commands = [
        BotCommand(command="start",  description="🏠 Главное меню"),
        BotCommand(command="admin",  description="👑 Панель администратора"),
    ]
    for aid in ADMIN_IDS:
        try:
            await bot.set_my_commands(
                admin_commands,
                scope=BotCommandScopeChat(chat_id=aid)
            )
        except Exception as e:
            print(f"[commands] admin {aid}: {e}")

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
    asyncio.create_task(scheduler(bot))

    await setup_commands(bot)
    print(f"Bot started | IMPORT_TOKEN={os.environ.get('IMPORT_TOKEN','secret123')}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
