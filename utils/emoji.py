# utils/emoji.py
EMOJI = {
    "catalog": {"id": "5278613311858959074", "fallback": "🛒"},
    "profile": {"id": "5275979556308674886", "fallback": "👤"},
    "replace": {"id": "5276240711795107620", "fallback": "⚠️"},
    "stock":   {"id": "5278540791336165644", "fallback": "📦"},
    "topup":   {"id": "5278411813468269386", "fallback": "✅"},
    "promo":   {"id": "5276422526350681413", "fallback": "🎁"},
    "history": {"id": "5278227821364275264", "fallback": "📁"},
    "support": {"id": "5276381204470329471", "fallback": "🧑‍💻"},
    "warning": {"id": "5276240711795107620", "fallback": "⚠️"},
    "ban":     {"id": "5278578973595427038", "fallback": "🚫"},
    "unban":   {"id": "5278602437001767574", "fallback": "🔓"},
    "star":    {"id": "5276111746812112286", "fallback": "⭐"},
    "time":    {"id": "5276412364458059956", "fallback": "🕓"},
    "buy":     {"id": "5278305362703835500", "fallback": "🔗"},
    "money":   {"id": "5278411813468269386", "fallback": "💰"},
}

def tg_emoji(emoji_key: str) -> str:
    data = EMOJI.get(emoji_key)
    if data:
        return f'<tg-emoji emoji-id="{data["id"]}">{data["fallback"]}</tg-emoji>'
    return "❓"
