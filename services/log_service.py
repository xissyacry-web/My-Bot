from config import LOG_CHAT_ID, pe

async def _log(bot, text: str):
    if not LOG_CHAT_ID or not bot:
        return
    try:
        await bot.send_message(LOG_CHAT_ID, text, parse_mode="HTML")
    except Exception as e:
        print(f"[LOG] {e}")

async def log_register(bot, user_id, username, ref_by=None):
    uname = f"@{username}" if username else f"id:{user_id}"
    msg = f"{pe('bell')} <b>Новый пользователь</b>\n{pe('user')} {uname} (<code>{user_id}</code>)"
    if ref_by:
        msg += f"\n{pe('link')} реферал от <code>{ref_by}</code>"
    await _log(bot, msg)

async def log_topup(bot, user_id, username, amount, asset):
    uname = f"@{username}" if username else f"id:{user_id}"
    await _log(bot, f"{pe('wallet')} <b>Пополнение</b>\n{pe('user')} {uname} (<code>{user_id}</code>)\n💰 +{amount:.2f}$ ({asset})")

async def log_purchase(bot, user_id, username, product_name, amount, total, cashback=0, lines=None):
    uname = f"@{username}" if username else f"id:{user_id}"
    msg = (f"{pe('box')} <b>Покупка</b>\n{pe('user')} {uname} (<code>{user_id}</code>)\n"
           f"{pe('briefcase')} <b>{product_name}</b> × {amount}\n{pe('wallet')} {total:.2f}$")
    if cashback:
        msg += f"  {pe('star')} кэшбек +{cashback:.4f}$"
    if lines:
        nums = "\n".join(f"  {i+1}. <code>{l}</code>" for i, l in enumerate(lines))
        msg += f"\n\n{pe('books')} <b>Выдано:</b>\n{nums}"
    await _log(bot, msg)

async def log_promo(bot, user_id, username, code, amount):
    uname = f"@{username}" if username else f"id:{user_id}"
    await _log(bot, f"{pe('gift')} <b>Промокод</b>\n{pe('user')} {uname} (<code>{user_id}</code>)\n<code>{code}</code> → +{amount:.2f}$")

async def log_broadcast(bot, admin_id, text, ok, fail):
    await _log(bot, f"{pe('mega')} <b>Рассылка</b>\nАдмин <code>{admin_id}</code>\n✅ {ok}  ❌ {fail}\n<i>{text[:80]}</i>")
