import os

BOT_TOKEN        = os.environ.get("BOT_TOKEN",        "8763758254:AAG9LQKq6KUDnLLv6BFc0hDNA7e7eJN1hLA")
CRYPTO_BOT_TOKEN = os.environ.get("CRYPTO_BOT_TOKEN", "588982:AARxXJtGOMKkXibK6z9yOogblUSEYerHJqD")
ADMIN_IDS_STR    = os.environ.get("ADMIN_IDS",        "1073780833")
ADMIN_IDS        = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip()]
DATABASE_URL     = os.environ.get("DATABASE_URL",     "sqlite+aiosqlite:///./bot.db")
BOT_USERNAME     = os.environ.get("BOT_USERNAME",     "XissyaLogBot")
LOG_CHAT_ID      = int(os.environ.get("LOG_CHAT_ID",  "-1003816125421"))
VERSION          = "v5.0.0"

CASHBACK_DEFAULT = float(os.environ.get("CASHBACK_PCT", "1.0"))
REF_BONUS        = float(os.environ.get("REF_BONUS",    "0.5"))
MIN_TOPUP        = float(os.environ.get("MIN_TOPUP",    "0.5"))

CRYPTO_ASSETS = ["USDT", "TON", "BTC", "ETH", "LTC", "BNB", "TRX"]

PREMIUM_EMOJI = {
    "heart":    ("5278611606756942667", "❤️"),
    "folder":   ("5278227821364275264", "📁"),
    "bookmark": ("5276111746812112286", "⭐️"),
    "unlock":   ("5278602437001767574", "🔓"),
    "shield":   ("5276262671962892944", "🛡"),
    "warning":  ("5276240711795107620", "⚠️"),
    "ban":      ("5278578973595427038", "🚫"),
    "monitor":  ("5278647306525108244", "🖥"),
    "info":     ("5278753302023004775", "ℹ️"),
    "mega":     ("5278528159837348960", "📢"),
    "check":    ("5278411813468269386", "✅"),
    "cart":     ("5278613311858959074", "🛒"),
    "trash":    ("5276384644739129761", "🗑"),
    "clock":    ("5276412364458059956", "🕓"),
    "briefcase":("5276037216244624892", "💼"),
    "search":   ("5276395476646653290", "🔍"),
    "palette":  ("5276442772826515132", "🎨"),
    "user":     ("5275979556308674886", "👤"),
    "users":    ("5298668674532538341", "👥"),
    "dev":      ("5276381204470329471", "🧑‍💻"),
    "wallet":   ("5276398496008663230", "👝"),
    "mail":     ("5278589204207528856", "📨"),
    "crown":    ("5276229330131772747", "👑"),
    "box":      ("5278540791336165644", "📦"),
    "link":     ("5278305362703835500", "🔗"),
    "hammer":   ("5276314275994954605", "🔨"),
    "gift":     ("5276422526350681413", "🎁"),
    "gamepad":  ("5278304890257436355", "🎮"),
    "chart":    ("5278778882848220741", "📊"),
    "home":     ("5278413853577734640", "🏠"),
    "robot":    ("5276127848644503161", "🤖"),
    "download": ("5276220667182736079", "📥"),
    "star":     ("5206476089127372379", "⭐️"),
    "books":    ("5206626000665868017", "📚"),
    "up":       ("5206401524200145033", "🔼"),
    "down":     ("5206510891247371052", "🔽"),
    "box2":     ("5206702193385700709", "📦"),
    "lab":      ("5206211858444354221", "🧪"),
    "compass":  ("5206202791768393003", "🧭"),
    "bell":     ("5206222720416643915", "🔔"),
    "coin_ton":  ("5193179982775476271", "🪙"),
    "coin_btc":  ("5195107400889163662", "🪙"),
    "coin_eth":  ("5194983413773266305", "🪙"),
    "coin_usdt": ("5192942020112442148", "🪙"),
    "coin_ltc":  ("5193059508942824703", "🪙"),
    "coin_bnb":  ("5193004361562745352", "🪙"),
    "coin_trx":  ("5195352119535755156", "🪙"),
    "coin_sol":  ("5192685687874280710", "🪙"),
    "n0": ("5242380641332393116", "0️⃣"),
    "n1": ("5244961448525848230", "1️⃣"),
    "n2": ("5242293676834579345", "2️⃣"),
    "n3": ("5242652525647127686", "3️⃣"),
    "n4": ("5242287453426969423", "4️⃣"),
    "n5": ("5242407832770340528", "5️⃣"),
    "n6": ("5242669447818277073", "6️⃣"),
    "n7": ("5242663134216350272", "7️⃣"),
    "n8": ("5242497782270418294", "8️⃣"),
    "n9": ("5242286371095211663", "9️⃣"),
    "plus":  ("5242329690135356589", "➕"),
    "minus": ("5244796895443838315", "➖"),
    "star2": ("5242612543796567211", "⭐️"),
    "excl":  ("5242578970037218790", "❕"),
    "quest": ("5242205011529719330", "❔"),
    "text":  ("5242602592357345985", "🔤"),
    "cur_usd": ("5255933397750014894", "💱"),
    "cur_eur": ("5256008271914885402", "💱"),
    "cur_rub": ("5255806447106679302", "💱"),
    "cur_gbp": ("5255845368100317401", "💱"),
    "cur_jpy": ("5258157739837779860", "💱"),
    "cur_cny": ("5256030713119007739", "💱"),
    "cur_uah": ("5255828733691981585", "💱"),
    "cur_kzt": ("5255787742524103649", "💱"),
}

def pe(key: str) -> str:
    if key not in PREMIUM_EMOJI:
        return ""
    eid, fallback = PREMIUM_EMOJI[key]
    return f'<tg-emoji emoji-id="{eid}">{fallback}</tg-emoji>'

def pe_num(n: int) -> str:
    keys = ["n0","n1","n2","n3","n4","n5","n6","n7","n8","n9"]
    return pe(keys[n]) if 0 <= n <= 9 else str(n)

def pe_coin(asset: str) -> str:
    mapping = {
        "TON": "coin_ton", "BTC": "coin_btc", "ETH": "coin_eth",
        "USDT": "coin_usdt", "LTC": "coin_ltc", "BNB": "coin_bnb",
        "TRX": "coin_trx", "SOL": "coin_sol",
    }
    return pe(mapping.get(asset.upper(), "coin_usdt"))
PYEOF
echo "ok"
