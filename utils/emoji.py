# ID премиум-эмодзи из проверенного источника
EMOJI = {
    "catalog": "5278613311858959074",   # 🛒
    "profile": "5275979556308674886",   # 👤
    "replace": "5276240711795107620",   # ⚠️
    "stock": "5278540791336165644",     # 📦
    "topup": "5278411813468269386",     # ✅
    "promo": "5276422526350681413",     # 🎁
    "history": "5278227821364275264",   # 📁
    "support": "5276381204470329471",   # 🧑‍💻
    "warning": "5276240711795107620",
    "ban": "5278578973595427038",
    "unban": "5278602437001767574",
    "star": "5276111746812112286",
    "time": "5276412364458059956",
    "buy": "5278305362703835500",
    "money": "5278411813468269386",
}

def tg_emoji(emoji_key: str, fallback: str = "❓") -> str:
    emoji_id = EMOJI.get(emoji_key)
    if emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'
    return fallback
