import aiohttp
from config import CRYPTO_BOT_TOKEN, BOT_USERNAME

API_BASE = "https://pay.crypt.bot/api"

async def create_invoice(amount: float, description: str = "Пополнение баланса") -> dict:
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    payload = {
        "asset": "USDT",
        "amount": str(amount),
        "description": description,
        "paid_btn_name": "callback",
        "paid_btn_url": f"https://t.me/{BOT_USERNAME}"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{API_BASE}/createInvoice", json=payload, headers=headers) as resp:
            data = await resp.json()
            if data.get("ok"):
                return data["result"]
            else:
                error = data.get("error", {})
                if error.get("name") == "AMOUNT_TOO_SMALL":
                    min_amount = error.get("min_invoice_amount_in_usd", 0.01)
                    raise Exception(f"Минимальная сумма пополнения: {min_amount} USDT")
                else:
                    raise Exception(f"Ошибка Crypto Bot: {error.get('name', 'неизвестная ошибка')}")

async def get_invoice(invoice_id: int) -> dict:
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE}/getInvoices", params={"invoice_ids": invoice_id}, headers=headers) as resp:
            data = await resp.json()
            if data.get("ok") and data["result"]["items"]:
                return data["result"]["items"][0]
            return None

async def check_pending_invoices(invoice_ids: list[int]) -> dict:
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    ids_str = ",".join(map(str, invoice_ids))
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE}/getInvoices", params={"invoice_ids": ids_str}, headers=headers) as resp:
            data = await resp.json()
            if data.get("ok"):
                return {inv["invoice_id"]: inv["status"] for inv in data["result"]["items"]}
            return {}
