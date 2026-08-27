from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


# Подпись кнопки статуса под опубликованным постом.
STATUS_TEXT = {True: '✅ Актуально', False: '❌ Неактуально'}

# Переключатель закрепа при создании анкеты. Показывается только подписчикам.
PIN_TEXT = {False: '📌 Закреплять: да', True: '📌 Закреплять: нет'}

# Кнопка подписок в главном меню — текст нужен и хендлеру, и текстам писем о продлении.
SUB_BUTTON = '💎 Подписка ✨'

# Названия, цены и значки уровней. Единственное место, где написаны деньги.
SUB_TITLE = {'basic': 'Базовая', 'pro': 'Продвинутая'}
SUB_PRICE = {'basic': '49.99 ₽', 'pro': '111 ₽'}
SUB_ICON = {'basic': '🌸', 'pro': '👑'}


def _reply(*rows: list[str], **kwargs) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text) for text in row] for row in rows],
        resize_keyboard=True,
        **kwargs,
    )


def main_keyboard():
    return _reply(
        ['📝 Анкета 💖'],
        ['👤 Профиль ✨', SUB_BUTTON],
        ['📜 Правила ✨', '📞 Прямая связь 💖'],
        one_time_keyboard=True,
    )


def accetp_keyboard(pin: bool | None = None):
    """Подтверждение анкеты. pin=None — человек без подписки, кнопки закрепа у него нет."""
    rows = [['✅ Верно 💖']]
    if pin is not None:
        rows.append([PIN_TEXT[bool(pin)]])
    rows.append(['🔄 Переделать анкету ✨'])
    return _reply(*rows)


def acetp_keyboard(post_id: str):
    """Кнопки модерации. id работы едет в callback_data, чтобы старые сообщения тоже находили свой пост."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='✅ Одобрить', callback_data=f'approve:{post_id}')],
        [InlineKeyboardButton(text='❌ Отклонить', callback_data=f'reject:{post_id}')],
    ])


def post_keyboard(actual: bool, author_url: str):
    """Одна кнопка под постом: показывает статус работы и ведёт к автору."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f'{STATUS_TEXT[bool(actual)]} · написать автору', url=author_url)],
    ])


def works_keyboard(items: list[tuple[str, str]]):
    """Список последних работ в профиле: items — пары (id работы, подпись кнопки)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        *([InlineKeyboardButton(text=label, callback_data=f'work:{post_id}')] for post_id, label in items),
        [InlineKeyboardButton(text='🔙 Назад ✨', callback_data='profile:close')],
    ])


def work_keyboard(post_id: str):
    """Кнопки под выбранной работой в профиле."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🔔 Напоминалка', callback_data=f'remind:{post_id}')],
        [InlineKeyboardButton(text='✅ Актуально', callback_data=f'act:{post_id}:1'),
         InlineKeyboardButton(text='❌ Неактуально', callback_data=f'act:{post_id}:0')],
    ])


def _buy(tier: str, label: str):
    return InlineKeyboardButton(text=f'{SUB_ICON[tier]} {label} — {SUB_PRICE[tier]}',
                                callback_data=f'sub:buy:{tier}')


def sub_menu_keyboard(tier: str = ''):
    """Выбор подписки. Набор кнопок зависит от того, что у человека уже есть."""
    if tier == 'pro':
        rows = [[_buy('pro', 'Продлить на 30 дней')],
                [InlineKeyboardButton(text='✏️ Сменить префикс', callback_data='sub:prefix')]]
    elif tier == 'basic':
        rows = [[_buy('basic', 'Продлить на 30 дней')],
                [_buy('pro', 'Перейти на продвинутую')]]
    else:
        rows = [[_buy('basic', 'Базовая')],
                [_buy('pro', 'Продвинутая')]]

    rows.append([InlineKeyboardButton(text='🔙 Закрыть', callback_data='sub:close')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pay_keyboard(tier: str):
    """Экран оплаты: подтверждение перевода и возврат к выбору подписки."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='✅ Оплатил', callback_data=f'sub:paid:{tier}')],
        [InlineKeyboardButton(text='🔙 Назад', callback_data='sub:menu')],
    ])


def sub_request_keyboard(request_id: str):
    """Заявка на подписку в админском чате."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='✅ Одобрить', callback_data=f'subok:{request_id}')],
        [InlineKeyboardButton(text='❌ Отклонить', callback_data=f'subno:{request_id}')],
    ])


def prefix_keyboard(user_id: int):
    """Заявка на свой префикс в админском чате."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='✅ Разрешить', callback_data=f'pfxok:{user_id}')],
        [InlineKeyboardButton(text='❌ Отклонить', callback_data=f'pfxno:{user_id}')],
    ])


def ads_keyboard(count: int):
    """Управление рекламными цитатами: удаление по номеру и добавление новой."""
    numbers = [InlineKeyboardButton(text=f'🗑 {i + 1}', callback_data=f'ad:del:{i}') for i in range(count)]
    rows = [numbers[i:i + 4] for i in range(0, len(numbers), 4)]
    rows.append([InlineKeyboardButton(text='➕ Добавить цитату', callback_data='ad:add')])
    rows.append([InlineKeyboardButton(text='🔙 Закрыть', callback_data='ad:close')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def move_nazad():
    return _reply(['🔙 Назад ✨'])


def admin_keyboard():
    return _reply(
        ['📊 Статистика', '📣 Рассылка'],
        ['✉️ Написать пользователю', '📤 В группу'],
        ['📢 Реклама', '💎 Подписки'],
        ['🔙 Выйти'],
        one_time_keyboard=False,
    )
