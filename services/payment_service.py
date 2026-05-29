import aiohttp
from config import CRYPTO_BOT_TOKEN

API_BASE = "https://pay.crypt.bot/api"

async def create_invoice(amount: float, description: str = "Пополнение баланса") -> dict:
    """Создать инвойс через Crypto Bot API, возвращает данные инвойса"""
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    payload = {
        "asset": "USDT",          # или "TON", "BTC" и т.д. Можно сделать выбор
        "amount": str(amount),
        "description": description,
        "paid_btn_name": "callback",
        "paid_btn_url": "https://t.me/your_bot"  # необязательно
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{API_BASE}/createInvoice", json=payload, headers=headers) as resp:
            data = await resp.json()
            if data.get("ok"):
                return data["result"]
            else:
                raise Exception(f"Crypto Bot error: {data}")

async def get_invoice(invoice_id: int) -> dict:
    """Получить статус конкретного инвойса"""
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE}/getInvoices", params={"invoice_ids": invoice_id}, headers=headers) as resp:
            data = await resp.json()
            if data.get("ok") and data["result"]["items"]:
                return data["result"]["items"][0]
            return None

async def check_pending_invoices(invoice_ids: list[int]) -> dict:
    """Массовая проверка статусов инвойсов"""
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE}/getInvoices", params={"invoice_ids": ",".join(map(str, invoice_ids))}, headers=headers) as resp:
            data = await resp.json()
            if data.get("ok"):
                return {inv["invoice_id"]: inv["status"] for inv in data["result"]["items"]}
            return {}
