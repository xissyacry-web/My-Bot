def get_emoji(char: str, emoji_id: str) -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{char}</tg-emoji>'

class Emojis:
    @property
    def HEART(self): return get_emoji("❤️", "5278611606756942667")
    @property
    def CATALOG(self): return get_emoji("📁", "5278227821364275264")
    @property
    def STAR_GOLD(self): return get_emoji("⭐️", "5276111746812112286")
    @property
    def REPLACE(self): return get_emoji("💱", "5255933397750014894")
    @property
    def MIRRORS(self): return get_emoji("🔗", "5278305362703835500")
    @property
    def PROFILE(self): return get_emoji("👤", "5275979556308674886")
    @property
    def LOCK_OPEN(self): return get_emoji("🔓", "5278602437001767574")
    @property
    def SHIELD(self): return get_emoji("🛡", "5276262671962892944")
    @property
    def WARNING(self): return get_emoji("⚠️", "5276240711795107620")
    @property
    def BAN(self): return get_emoji("🚫", "5278578973595427038")
    @property
    def INFO(self): return get_emoji("ℹ️", "5278753302023004775")
    @property
    def ALERT(self): return get_emoji("📢", "5278528159837348960")
    @property
    def CHECK(self): return get_emoji("✅", "5278411813468269386")
    @property
    def CART(self): return get_emoji("🛒", "5278613311858959074")
    @property
    def CLOCK(self): return get_emoji("🕓", "5276412364458059956")
    @property
    def BOX_1(self): return get_emoji("📦", "5278540791336165644")
    @property
    def COIN_1(self): return get_emoji("🪙", "5193179982775476271")
    @property
    def EMPTY(self): return get_emoji("📁", "5278227821364275264")
    @property
    def NUM_1(self): return get_emoji("1️⃣", "5244961448525848230")
    # При необходимости добавьте остальные свойства по аналогии
