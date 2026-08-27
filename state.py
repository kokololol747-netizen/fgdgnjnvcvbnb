from aiogram.fsm.state import State, StatesGroup


class anket(StatesGroup):
    photo = State()
    info = State()


class SubPrefix(StatesGroup):
    """Продвинутый подписчик придумывает себе префикс — дальше его смотрит админ."""
    waiting_text = State()


class AdminBroadcast(StatesGroup):
    waiting_text = State()


class AdminMessage(StatesGroup):
    target = State()
    text = State()


class AdminGroupMessage(StatesGroup):
    waiting_text = State()


class AdminAd(StatesGroup):
    """Админ вводит новую рекламную цитату."""
    waiting_text = State()
