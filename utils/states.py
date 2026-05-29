from aiogram.fsm.state import State, StatesGroup

class ReplenishBalance(StatesGroup):
    amount = State()

class PromocodeInput(StatesGroup):
    code = State()

class ReplaceRequestStates(StatesGroup):
    phone_number = State()
    date_time = State()

class BuyProduct(StatesGroup):
    product_id = State()
    amount = State()

class AdminAddProduct(StatesGroup):
    category_id = State()
    name = State()
    quantity = State()
    price = State()
    content = State()

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
