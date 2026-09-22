from aiogram.fsm.state import State, StatesGroup

class TestState(StatesGroup):
    question = State()
    test = State()
    result = State()
