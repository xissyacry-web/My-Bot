import os

BOT_TOKEN        = os.environ.get("BOT_TOKEN",        "8763758254:AAG9LQKq6KUDnLLv6BFc0hDNA7e7eJN1hLA")
CRYPTO_BOT_TOKEN = os.environ.get("CRYPTO_BOT_TOKEN", "588982:AArdcMSbXObb22HJ4CCerqfmx9cVFdBXq0a")
ADMIN_IDS        = [int(x) for x in os.environ.get("ADMIN_IDS", "1073780833").split(",") if x.strip()]
DATABASE_URL     = os.environ.get("DATABASE_URL",     "sqlite+aiosqlite:///./bot.db")
BOT_USERNAME     = os.environ.get("BOT_USERNAME",     "XissyaLogBot")
LOG_CHAT_ID      = int(os.environ.get("LOG_CHAT_ID",  "-1003816125421") or 0)
IMPORT_TOKEN     = os.environ.get("IMPORT_TOKEN",     "secret123")
VERSION          = "v6.0.0"

CASHBACK_DEFAULT = 1.0   # % кэшбека по умолчанию
REF_BONUS_PCT    = 10.0  # % от пополнения реферала → пригласившему
MIN_TOPUP        = 0.5

CRYPTO_ASSETS = ["USDT", "TON", "BTC", "ETH", "LTC", "BNB", "TRX"]

# Все 40 премиум эмодзи из Translucent Pack by @v7agency
E = {
    "heart":     ("5278611606756942667", "❤️"),
    "folder":    ("5278227821364275264", "📁"),
    "star":      ("5276111746812112286", "⭐️"),
    "unlock":    ("5278602437001767574", "🔓"),
    "shield":    ("5276262671962892944", "🛡"),
    "warning":   ("5276240711795107620", "⚠️"),
    "ban":       ("5278578973595427038", "🚫"),
    "monitor":   ("5278647306525108244", "🖥"),
    "info":      ("5278753302023004775", "ℹ️"),
    "mega":      ("5278528159837348960", "📢"),
    "check":     ("5278411813468269386", "✅"),
    "cart":      ("5278613311858959074", "🛒"),
    "trash":     ("5276384644739129761", "🗑"),
    "clock":     ("5276412364458059956", "🕓"),
    "briefcase": ("5276037216244624892", "💼"),
    "search":    ("5276395476646653290", "🔍"),
    "palette":   ("5276442772826515132", "🎨"),
    "user":      ("5275979556308674886", "👤"),
    "users":     ("5298668674532538341", "👥"),
    "dev":       ("5276381204470329471", "🧑‍💻"),
    "wallet":    ("5276398496008663230", "👝"),
    "mail":      ("5278589204207528856", "📨"),
    "crown":     ("5276229330131772747", "👑"),
    "box":       ("5278540791336165644", "📦"),
    "link":      ("5278305362703835500", "🔗"),
    "hammer":    ("5276314275994954605", "🔨"),
    "gift":      ("5276422526350681413", "🎁"),
    "gamepad":   ("5278304890257436355", "🎮"),
    "chart":     ("5278778882848220741", "📊"),
    "home":      ("5278413853577734640", "🏠"),
    "robot":     ("5276127848644503161", "🤖"),
    "download":  ("5276220667182736079", "📥"),
    "star2":     ("5206476089127372379", "⭐️"),
    "books":     ("5206626000665868017", "📚"),
    "up":        ("5206401524200145033", "🔼"),
    "down":      ("5206510891247371052", "🔽"),
    "box2":      ("5206702193385700709", "📦"),
    "lab":       ("5206211858444354221", "🧪"),
    "compass":   ("5206202791768393003", "🧭"),
    "bell":      ("5206222720416643915", "🔔"),
}

def pe(key: str) -> str:
    """Премиум эмодзи для сообщений (parse_mode=HTML)"""
    if key not in E: return ""
    eid, fb = E[key]
    return f'<tg-emoji emoji-id="{eid}">{fb}</tg-emoji>'

ASSET_EMOJI = {"USDT":"💵","TON":"💎","BTC":"🟡","ETH":"🔷","LTC":"⚪","BNB":"🟠","TRX":"🔴"}
def pe_coin(asset: str) -> str:
    """Возвращает эмодзи для криптовалютного актива"""
    return ASSET_EMOJI.get(asset, "🪙")

def pe_num(number: int) -> str:
    """Трансформирует цифры в эмодзи-цифры (например, для топ-списков)"""
    num_map = {"0":"0️⃣","1":"1️⃣","2":"2️⃣","3":"3️⃣","4":"4️⃣","5":"5️⃣","6":"6️⃣","7":"7️⃣","8":"8️⃣","9":"9️⃣"}
    return "".join(num_map.get(char, char) for char in str(number))
