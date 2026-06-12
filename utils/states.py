from aiogram.fsm.state import State, StatesGroup

class ReplenishBalance(StatesGroup):
    asset  = State()
    amount = State()

class PromocodeInput(StatesGroup):
    code = State()

class ReplaceRequestStates(StatesGroup):
    log_time  = State()
    photos    = State()
    complaint = State()

class BuyProduct(StatesGroup):
    amount = State()

class ReviewStates(StatesGroup):
    rating = State()
    text   = State()

class UnbanProcess(StatesGroup):
    waiting_photos      = State()
    waiting_description = State()
    confirm             = State()

class AdminAddProduct(StatesGroup):
    category_id = State()
    name        = State()
    description = State()
    price       = State()
    quantity    = State()
    content     = State()
    file        = State()

class AdminEditDesc(StatesGroup):
    category_id = State()
    product_id  = State()
    new_desc    = State()

class AdminEditPrice(StatesGroup):
    category_id = State()
    product_id  = State()
    new_price   = State()

class AdminBulkPrice(StatesGroup):
    action = State()   # percent or fixed

class AdminAddCategory(StatesGroup):
    name      = State()
    parent_id = State()

class AdminDeleteProduct(StatesGroup):
    category_id = State()
    product_id  = State()

class AdminDeleteCategory(StatesGroup):
    category_id = State()

class AdminDeleteLines(StatesGroup):
    category_id = State()
    product_id  = State()
    lines       = State()

class AdminPromoAdd(StatesGroup):
    code            = State()
    amount          = State()
    max_activations = State()
    expires_days    = State()

class AdminPromoDelete(StatesGroup):
    code = State()

class AdminUserSearch(StatesGroup):
    user_id = State()

class AdminUserBalance(StatesGroup):
    user_id = State()
    amount  = State()

class AdminUserBan(StatesGroup):
    user_id = State()
    reason  = State()

class AdminUserCashback(StatesGroup):
    user_id = State()
    pct     = State()

class AdminBroadcast(StatesGroup):
    message  = State()
    schedule = State()   # дата/время или "now"

class AdminReplaceApprove(StatesGroup):
    message = State()

class AdminReplaceReject(StatesGroup):
    reason = State()

class AdminRefillProduct(StatesGroup):
    category_id = State()
    product_id  = State()
    content     = State()

class AdminBulkProduct(StatesGroup):
    category_id = State()
    product_id  = State()
    file        = State()

class AdminImport(StatesGroup):
    file = State()

class AdminViewLogs(StatesGroup):
    user_id = State()
