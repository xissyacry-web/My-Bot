from aiogram.fsm.state import State, StatesGroup

class ReplenishBalance(StatesGroup):
    amount = State()

class PromocodeInput(StatesGroup):
    code = State()

class ReplaceRequestStates(StatesGroup):
    phone_number = State()
    date_time = State()

class AdminAddProduct(StatesGroup):
    category_id = State()
    name = State()
    price = State()
    file = State

class AdminEditProduct(StatesGroup):
    product_id = State()
    field = State()
    value = State()

class AdminManageUser(StatesGroup):
    user_id = State()
    action = State()
    amount = State()
