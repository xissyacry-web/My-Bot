import aiohttp
from config import CRYPTO_BOT_TOKEN, BOT_USERNAME, CRYPTO_ASSETS

API_BASE = "https://pay.crypt.bot/api"

async def create_invoice(amount: float, description: str = "Пополнение", asset: str = "USDT") -> dict:
    if asset not in CRYPTO_ASSETS:
        asset = "USDT"
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    payload = {
        "asset": asset,
        "amount": str(round(amount, 8)),
        "description": description,
        "paid_btn_name": "callback",
        "paid_btn_url": f"https://t.me/{BOT_USERNAME}",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{API_BASE}/createInvoice", json=payload, headers=headers) as resp:
            data = await resp.json()
            if data.get("ok"):
                return data["result"]
            err = data.get("error", {})
            if err.get("name") == "AMOUNT_TOO_SMALL":
                raise Exception("Слишком маленькая сумма для выбранной валюты.")
            raise Exception(f"CryptoBot: {err.get('name', 'неизвестная ошибка')}")

async def get_invoice(invoice_id: int) -> dict | None:
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{API_BASE}/getInvoices",
            params={"invoice_ids": invoice_id},
            headers=headers
        ) as resp:
            data = await resp.json()
            if data.get("ok") and data["result"]["items"]:
                return data["result"]["items"][0]
    return None

async def get_exchange_rates() -> dict:
    """Возвращает курсы крипты к USD"""
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE}/getExchangeRates", headers=headers) as resp:
            data = await resp.json()
            if data.get("ok"):
                rates = {}
                for item in data["result"]:
                    if item.get("target") == "USD" and item.get("is_valid"):
                        rates[item["source"]] = float(item["rate"])
                return rates
    return {}
