from aiogram.fsm.state import State, StatesGroup

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
    photos = State()
    reason = State()
    confirm = State()

# Admin states
class AddProduct(StatesGroup):
    cat_id = State(); name = State(); desc = State()
    price  = State(); qty  = State(); content = State(); file = State()

class EditDesc(StatesGroup):
    cat_id = State(); prod_id = State(); text = State()

class EditPrice(StatesGroup):
    cat_id = State(); prod_id = State(); price = State()

class BulkPrice(StatesGroup):
    action = State()

class RefillProduct(StatesGroup):
    cat_id = State(); prod_id = State(); content = State()

class BulkTxt(StatesGroup):
    cat_id = State(); prod_id = State(); file = State()

class DeleteLines(StatesGroup):
    cat_id = State(); prod_id = State(); lines = State()

class AddCategory(StatesGroup):
    name   = State()
    parent = State()

class DelProduct(StatesGroup):
    cat_id = State(); prod_id = State()

class DelCategory(StatesGroup):
    cat_id = State()

class UserFind(StatesGroup):
    uid = State()

class UserBal(StatesGroup):
    uid = State(); amount = State()

class UserBan(StatesGroup):
    uid = State(); reason = State()

class UserCashback(StatesGroup):
    uid = State(); pct = State()

class PromoAdd(StatesGroup):
    code = State(); amount = State(); max_uses = State(); days = State()

class PromoDel(StatesGroup):
    code = State()

class Broadcast(StatesGroup):
    text     = State()
    schedule = State()

class ReplaceApprove(StatesGroup):
    msg = State()

class ReplaceReject(StatesGroup):
    reason = State()

class ImportDB(StatesGroup):
    file = State()

class ViewLogs(StatesGroup):
    uid = State()
