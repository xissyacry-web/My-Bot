def get_emoji(char: str, emoji_id: str) -> str:
    """Создаёт HTML-тег для кастомного эмодзи"""
    return f'<tg-emoji emoji-id="{emoji_id}">{char}</tg-emoji>'

class Emojis:
    # Главные разделы интерфейса
    HEART = get_emoji("❤️", "5278611606756942667")
    CATALOG = get_emoji("📁", "5278227821364275264")
    STAR_GOLD = get_emoji("⭐️", "5276111746812112286")
    REPLACE = get_emoji("💱", "5255933397750014894")
    MIRRORS = get_emoji("🔗", "5278305362703835500")
    PROFILE = get_emoji("👤", "5255806447106679302")
    
    # Системные статусы и уведомления
    LOCK_OPEN = get_emoji("🔓", "5278602437001767574")
    SHIELD = get_emoji("🛡", "5276262671962892944")
    WARNING = get_emoji("⚠️", "5276240711795107620")
    BAN = get_emoji("🚫", "5278578973595427038")
    INFO = get_emoji("ℹ️", "5278753302023004775")
    ALERT = get_emoji("📢", "5278528159837348960")
    CHECK = get_emoji("✅", "5278411813468269386")
    CART = get_emoji("🛒", "5278613311858959074")
    TRASH = get_emoji("🗑", "5276384644739129761")
    CLOCK = get_emoji("🕓", "5276412364458059956")
    SEARCH = get_emoji("🔍", "5276395476646653290")
    
    # Продукты / Категории / Навигация
    BOX_1 = get_emoji("📦", "5278540791336165644")
    BOX_2 = get_emoji("📦", "5206702193385700709")
    UP = get_emoji("🔼", "5206401524200145033")
    DOWN = get_emoji("🔽", "5206510891247371052")
    LAB = get_emoji("🧪", "5206211858444354221")
    COMPASS = get_emoji("🧭", "5206202791768393003")
    BELL = get_emoji("🔔", "5206222720416643915")
    
    # Монеты и балансы
    COIN_1 = get_emoji("🪙", "5193179982775476271")
    COIN_2 = get_emoji("🪙", "5195107400889163662")
    COIN_3 = get_emoji("🪙", "5194983413773266305")
    
    # Банки и Логи (идеально для категорий MTS, Megafon, Yota, CryptoBot)
    BANK_MTS = get_emoji("🏦", "5192689390136089826")
    BANK_MEGA = get_emoji("🏦", "5194996633682600894")
    BANK_YOTA = get_emoji("🏦", "5192751963514625238")
    BANK_CRYPTO = get_emoji("🏦", "5193115240438455906")
    
    # Цифровые плашки (для вывода штук, позиций, лимитов)
    NUM_0 = get_emoji("0️⃣", "5242380641332393116")
    NUM_1 = get_emoji("1️⃣", "5244961448525848230")
    NUM_2 = get_emoji("2️⃣", "5242293676834579345")
    NUM_3 = get_emoji("3️⃣", "5242652525647127686")
    
    # Знаки операций
    PLUS = get_emoji("➕", "5242329690135356589")
    MINUS = get_emoji("➖", "5244796895443838315")
    Q_MARK = get_emoji("❔", "5242205011529719330")
    
    # Новые (навигация и история)
    BACK = get_emoji("⬆️", "5206401524200145033")
    HISTORY = get_emoji("📜", "5278227821364275264")
    OPERATIONS = get_emoji("🔄", "5255933397750014894")
    EMPTY = get_emoji("📂", "5278227821364275264")
