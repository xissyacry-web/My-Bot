from aiogram.fsm.state import State, StatesGroup

class CaptchaState(StatesGroup):
    waiting = State()

class BuyState(StatesGroup):
    amount = State()

class TopupState(StatesGroup):
    asset  = State()
    amount = State()

class PromoState(StatesGroup):
    code = State()

class ReviewState(StatesGroup):
    rating = State()
    text   = State()

class ReplaceState(StatesGroup):
    log    = State()
    photos = State()
    text   = State()

class UnbanState(StatesGroup):
    photos  = State()
    reason  = State()
    confirm = State()

class ReplaceApprove(StatesGroup):
    msg = State()

class ReplaceReject(StatesGroup):
    reason = State()

# ── ADMIN ─────────────────────────────────────────────────────────────────────
class AddProduct(StatesGroup):
    category_id = State()
    name        = State()
    description = State()
    price       = State()
    quantity    = State()
    content     = State()
    file        = State()

class EditDesc(StatesGroup):
    category_id = State()
    product_id  = State()
    text        = State()

class EditPrice(StatesGroup):
    category_id = State()
    product_id  = State()
    price       = State()

class BulkPrice(StatesGroup):
    action = State()

class RefillProduct(StatesGroup):
    category_id = State()
    product_id  = State()
    content     = State()

class BulkTxt(StatesGroup):
    category_id = State()
    product_id  = State()
    file        = State()

class DeleteLines(StatesGroup):
    category_id = State()
    product_id  = State()
    lines       = State()

class AddCategory(StatesGroup):
    name      = State()
    parent_id = State()

class DelProduct(StatesGroup):
    category_id = State()
    product_id  = State()

class DelCategory(StatesGroup):
    category_id = State()

class UserFind(StatesGroup):
    user_id = State()

class UserBal(StatesGroup):
    user_id = State()
    amount  = State()

class UserBan(StatesGroup):
    user_id = State()
    reason  = State()

class UserCashback(StatesGroup):
    user_id = State()
    pct     = State()

class PromoAdd(StatesGroup):
    code     = State()
    amount   = State()
    max_uses = State()
    days     = State()

class PromoDel(StatesGroup):
    code = State()

class Broadcast(StatesGroup):
    text     = State()
    schedule = State()

class ImportDB(StatesGroup):
    file = State()

class ViewLogs(StatesGroup):
    user_id = State()
