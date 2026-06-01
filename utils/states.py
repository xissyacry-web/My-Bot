from aiogram.fsm.state import State, StatesGroup

class ReplenishBalance(StatesGroup):
    amount = State()

class PromocodeInput(StatesGroup):
    code = State()

class ReplaceRequestStates(StatesGroup):
    log_time = State()
    photos = State()

class BuyProduct(StatesGroup):
    product_id = State()
    amount = State()

class UnbanProcess(StatesGroup):
    waiting_photos = State()
    waiting_done = State()
    waiting_description = State()
    confirm = State()

class AdminAddProduct(StatesGroup):
    category_id = State()
    name = State()
    description = State()
    price = State()
    quantity = State()
    content = State()
    file = State()

class AdminAddCategory(StatesGroup):
    name = State()
    parent_id = State()

class AdminDeleteProduct(StatesGroup):
    category_id = State()
    product_id = State()

class AdminDeleteCategory(StatesGroup):
    category_id = State()

class AdminPromoAdd(StatesGroup):
    code = State()
    amount = State()
    max_activations = State()
    expires_days = State()

class AdminPromoDelete(StatesGroup):
    code = State()

class AdminUserSearch(StatesGroup):
    user_id = State()

class AdminUserBalance(StatesGroup):
    user_id = State()
    amount = State()

class AdminUserBan(StatesGroup):
    user_id = State()
    reason = State()

class AdminBroadcast(StatesGroup):
    message = State()

class AdminReplaceApprove(StatesGroup):
    message = State()

class AdminReplaceReject(StatesGroup):
    reason = State()

class AdminRefillProduct(StatesGroup):
    category_id = State()
    product_id = State()
    content = State()

class AdminReplaceSelectPurchase(StatesGroup):
    purchase_id = State()
