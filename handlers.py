import asyncio
import html
import inspect
import json
import random
from contextlib import suppress
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (Message, ReplyKeyboardRemove, CallbackQuery, ReactionTypeEmoji,
                           FSInputFile)
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.filters.command import CommandStart, Command
from keyboard import (main_keyboard, accetp_keyboard, acetp_keyboard, post_keyboard, works_keyboard,
                      work_keyboard, move_nazad, admin_keyboard, sub_menu_keyboard, pay_keyboard,
                      sub_request_keyboard, prefix_keyboard, ads_keyboard,
                      PIN_TEXT, SUB_BUTTON, SUB_TITLE, SUB_PRICE, SUB_ICON)
from state import anket, AdminBroadcast, AdminMessage, AdminGroupMessage, AdminAd, SubPrefix


user = Router()
PUBLISH_CHAT_ID = -1003949770208
PUBLISH_CHANNEL_ID = -1003681963844
forwarding_sessions: dict[int, int] = {}
DATA_FILE = Path(__file__).with_name('bot_data.json')
ADMIN_IDS = {
    1830080090,  # Замените на id вашего администратора
}

IMAGE_DIR = Path(__file__).resolve().parent / 'image'

SUB_PHOTO = str(IMAGE_DIR / 'base.jpg')   # картинка на экране выбора подписки
PAY_PHOTO = str(IMAGE_DIR / 'base.jpg')   # картинка на экране оплаты (по задумке та же самая)
WAIT_PHOTO = str(IMAGE_DIR / 'basic.jpg')

# Реквизиты. Уходят человеку на экране оплаты как есть.
PAYMENT_DETAILS = ('Реквизиты для перевода:\n'
                   '💳 Карта: 40914810900026813293\n'
                   'Получатель: И.Зырянов\n\n'
                   'Переводи ровно указанную сумму, комментарий к переводу не нужен.')

# Сообщение-заглушка между «анкета создана» и решением админа.
# Оставишь и текст, и картинку пустыми - сообщение просто не отправится.
WAIT_TEXT = ('✨ Оформите подписку и ваша анкета будет самая первая опубликована.\n'
             'Чтобы оформить подписку, нажми кнопку «💎 Подписка ✨» 💖')
# ─────────────────────────────────────────────────────────────────────────────────

DEFAULT_DATA = {
    'users': {},
    'usage': {
        'buttons': {},
        'commands': {},
        'functions': {},
    },
    'broadcasts': [],
    'posts': {},           # id работы -> данные анкеты, см. cmd_confirm_anket
    'next_post_id': 1,
    'subs': {},            # id пользователя -> подписка, см. grant_sub
    'sub_requests': {},    # id заявки -> заявка на оплату, см. cb_sub_paid
    'next_sub_request_id': 1,
    'ads': [],             # рекламные цитаты; при первом запуске заполняются из DEFAULT_ADS
    'pins': [],            # закреплённые посты и время закрепа, чтобы снять через PIN_HOURS
}

# Рекламные цитаты по умолчанию. Меняются и удаляются из админки, здесь только первое наполнение.
DEFAULT_ADS = [
    'Не хочешь видеть этот блок под своим постом? Оформи подписку в боте: кнопка «💎 Подписка ✨».',
    'Наша флудилка: ',
    'Тут могла быть твоя реклама - условия у админа @toymaaa.',
    'Ищешь адопта? Листай канал целиком, новые работы выходят каждый день 💖',
]

PROFILE_WORKS = 5                             # сколько последних работ показывать в профиле
CAPTION_LIMIT = 850                           # запас от лимита Telegram в 1024 символа на подпись к фото:
                                              # сверху ещё лезут префикс, хештег и рекламная цитата
AD_LIMIT = 120                                # длина одной рекламной цитаты
PREFIX_LIMIT = 20                             # длина своего префикса у продвинутой подписки
REMINDER_COOLDOWN = timedelta(hours=24)       # как часто можно жать «Напоминалка»
BROADCAST_PAUSE = 0.05                        # пауза между сообщениями рассылки, чтобы не поймать 429
SUB_DAYS = 30                                 # срок подписки
SUB_WARN_DAYS = 2                             # за сколько дней предупредить об окончании
SUB_CHECK_PERIOD = 30 * 60                    # как часто наблюдатель проверяет подписки и закрепы
PIN_HOURS = 12                                # через сколько часов снимать закреп
PIN_TRIES = 3                                 # сколько раз пробовать снять закреп, если Telegram отказал

SUB_TIERS = {
    'basic': {
        'title': SUB_TITLE['basic'],
        'price': SUB_PRICE['basic'],
        'icon': SUB_ICON['basic'],
        'badge': 'няшка',                     # префикс фиксированный
        'tag': '#няшка',
        'reaction': '🔥',
        'priority': '⚡ Первый в модерации',
    },
    'pro': {
        'title': SUB_TITLE['pro'],
        'price': SUB_PRICE['pro'],
        'icon': SUB_ICON['pro'],
        'badge': 'VIP-котик',                 # стоит, пока человек не придумал свой префикс
        'tag': '#VIP_котик',
        'reaction': '🏆',
        'priority': '👑 Самый самый первый в модерации',
    },
}

SUB_PERKS = {
    'basic': (f'{SUB_ICON["basic"]} {SUB_TITLE["basic"]} - {SUB_PRICE["basic"]} / {SUB_DAYS} дней\n'
              '• префикс «няшка» над постом\n'
              '• хештег #няшка\n'
              '• под постом больше нет рекламной цитаты\n'
              f'• кнопка «закрепить пост» при создании анкеты (закреп держится {PIN_HOURS} часов)\n'
              '• реакция 🔥 от бота\n'
              '• первый в модерации'),
    'pro': (f'{SUB_ICON["pro"]} {SUB_TITLE["pro"]} - {SUB_PRICE["pro"]} / {SUB_DAYS} дней\n'
            '• префикс на выбор - свой текст\n'
            '• хештег #VIP_котик\n'
            '• под постом больше нет рекламной цитаты\n'
            f'• кнопка «закрепить пост» при создании анкеты (закреп держится {PIN_HOURS} часов)\n'
            '• реакция 🏆 от бота\n'
            '• самый самый первый в модерации'),
}

ANKET_PHOTO_PROMPT = '📸 Пришлите свою комишку или адопт 💖'
USER_NOT_FOUND = 'Пользователь не найден. Укажите ID или @username зарегистрированного пользователя.'
SEND_FAILED = 'Не удалось отправить сообщение. Возможно, пользователь заблокировал бота или указанный ID неверен.'
FORWARDING_ENABLED = ('Пересылка его следующих сообщений вам включена. '
                      'Пользователь может остановить пересылку, написав /start.')
WORK_NOT_FOUND = 'Работа не найдена. Открой профиль заново 💖'
PROFILE_HEADER = '🖼 Твои последние работы. Выбери любую, чтобы поднять её или поменять статус ✨'
PROFILE_EMPTY = ('🖼 Опубликованных работ пока нет.\n'
                 'Отправь анкету через «📝 Анкета 💖» - после одобрения она появится здесь ✨')
CHANNEL_UPDATE_FAILED = '⚠️ Статус сохранён, но пост в канале обновить не удалось - напиши админу.'
SUB_MENU_TAIL = ('Оплата обычным переводом: бот пришлёт реквизиты, а админ проверит перевод руками.\n'
                 f'Подписка включается сразу после проверки и действует {SUB_DAYS} дней.')
SUB_REQUEST_SENT = 'Заявка отправлена админу! Как проверит перевод - подписка включится и бот напишет ✨'
SUB_REQUEST_DOUBLE = 'Заявка уже отправлена, админ её скоро посмотрит 💖'
SUB_REQUEST_FAILED = ('⚠️ Не получилось отправить заявку админу. Напиши ему сам: @toymaaa - '
                      'или нажми «✅ Оплатил» ещё раз через минутку.')
SUB_REJECTED = ('💔 Оплата не подтвердилась.\n'
                'Если перевод точно был - напиши админу @toymaaa, он разберётся.')
PREFIX_PROMPT = ('✏️ Придумай свой префикс - его бот поставит над твоими постами.\n\n'
                 f'До {PREFIX_LIMIT} символов, одной строкой, без ссылок и упоминаний.\n'
                 'Админ его посмотрит и разрешит. Отменить - /cancel')
PREFIX_SENT = '✨ Префикс отправлен админу на проверку. Как разрешит - бот напишет 💖'
PREFIX_ONLY_PRO = 'Свой префикс - плюшка продвинутой подписки ✨'
MODERATION = {
    # action: (что написать автору, реакция на посте, подпись-фолбэк, ответ на нажатие кнопки)
    'approve': ('🎉 Ура! Твой арт прошёл модерацию! 💖', '🎉', '✅ Одобрено', 'Одобрено'),
    'reject': ('💔 Ой, к сожалению, твой артик не прошёл модерацию... ✨', '💔', '❌ Отклонено', 'Отклонено'),
}
ALREADY = {True: 'Ваша анкета и так актуальна', False: 'Ваша анкета и так неактуальна'}
STATUS_SET = {True: '✅ Работа отмечена как актуальная', False: '❌ Работа отмечена как неактуальная'}
STATUS_INFO = {True: '✅ Работа актуальна', False: '❌ Работа больше не актуальна'}
PIN_LABELS = set(PIN_TEXT.values())
ADMIN_ONLY_CLICK = 'Эта кнопка только для админов'


def merge_defaults(loaded, defaults):
    """Прочитанные данные поверх схемы по умолчанию: файл старой версии не уронит бота."""
    merged = deepcopy(defaults)
    for key, value in (loaded or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_defaults(value, merged[key])
        else:
            merged[key] = value
    return merged


def load_data():
    loaded = None
    if DATA_FILE.exists():
        with suppress(json.JSONDecodeError), DATA_FILE.open('r', encoding='utf-8') as f:
            loaded = json.load(f)

    merged = merge_defaults(loaded, DEFAULT_DATA)
    ids = [int(key) for key in merged['posts'] if str(key).isdigit()]
    merged['next_post_id'] = max([merged.get('next_post_id') or 1, *(i + 1 for i in ids)])

    request_ids = [int(key) for key in merged['sub_requests'] if str(key).isdigit()]
    merged['next_sub_request_id'] = max([merged.get('next_sub_request_id') or 1,
                                         *(i + 1 for i in request_ids)])
    if loaded is None or 'ads' not in loaded:
        # первый запуск (или файл от прошлой версии): пусть под постами сразу что-то было.
        # Дальше список правится из админки, и пустой он останется пустым.
        merged['ads'] = list(DEFAULT_ADS)
    return merged


def save_data(data):
    """Пишем через временный файл: падение в момент записи не оставит обрезанный JSON."""
    tmp = DATA_FILE.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(DATA_FILE)


data = load_data()


@user.message(F.chat.type == ChatType.PRIVATE)
async def forward_user_message(message: Message):
    if not message.from_user:
        raise SkipHandler()

    user_id = message.from_user.id
    admin_id = forwarding_sessions.get(user_id)
    if admin_id is None:
        raise SkipHandler()

    if message.text == '/start':
        forwarding_sessions.pop(user_id, None)
        with suppress(Exception):
            await message.bot.send_message(
                chat_id=admin_id,
                text=(
                    f'Пользователь {user_id} остановил пересылку, написав /start. '
                    'Пересылка завершена.'
                ),
            )
        return

    with suppress(Exception):
        if message.text:
            await message.bot.send_message(chat_id=admin_id, text=f'📩 Сообщение от {user_id}: {message.text}')
        elif message.photo:
            caption = message.caption or ''
            await message.bot.send_message(chat_id=admin_id, text=f'📩 Пользователь {user_id} прислал фото. {caption}')
            await message.bot.send_photo(chat_id=admin_id, photo=message.photo[-1].file_id, caption=caption)
        elif message.sticker:
            await message.bot.send_message(chat_id=admin_id, text=f'📩 Пользователь {user_id} прислал стикер.')
            await message.bot.send_sticker(chat_id=admin_id, sticker=message.sticker.file_id)
        else:
            await message.bot.send_message(
                chat_id=admin_id,
                text=f'📩 Пользователь {user_id} прислал сообщение типа {message.content_type}.',
            )


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def admin_only(warning: str | None = None):
    """Пускает в хендлер только админов. warning=None - чужие сообщения игнорируются молча.

    Обёртка принимает message позиционно, всё остальное - только именованно:
    вызывая такой хендлер из другого, пиши cmd_broadcast(message, state=state).
    """
    def decorator(handler):
        extra = set(inspect.signature(handler).parameters) - {'message'}

        @wraps(handler)
        async def wrapper(message: Message, **kwargs):
            if not is_admin(message.from_user.id if message.from_user else 0):
                if warning:
                    await message.answer(warning)
                return None
            return await handler(message, **{k: v for k, v in kwargs.items() if k in extra})

        return wrapper
    return decorator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(moment: datetime) -> str:
    """Время в том же виде, что и везде в файле: строки сравниваются как даты."""
    return moment.isoformat() + 'Z'


def _now() -> str:
    return _iso(_utcnow())


def tg_len(text: str) -> int:
    """Длина так, как её считает Telegram: в кодовых единицах UTF-16 (эмодзи весит 2)."""
    return len(text.encode('utf-16-le')) // 2


def tg_cut(text: str, limit: int) -> str:
    """Обрезает текст до limit единиц UTF-16, не разрубая эмодзи пополам."""
    return text.encode('utf-16-le')[:limit * 2].decode('utf-16-le', 'ignore')


async def reply_to_click(callback: CallbackQuery, text: str = '', alert: bool = True) -> None:
    """Ответ на нажатие кнопки.

    Отвечать надо быстро: Telegram держит запрос всего несколько секунд, а после рестарта бота
    в очереди могут лежать вообще просроченные нажатия. Просроченный запрос не считаем ошибкой -
    если текст важен, пишем его обычным сообщением в чат.
    """
    try:
        await callback.answer(text or None, show_alert=bool(text) and alert)
        return
    except TelegramBadRequest:
        pass
    except Exception:
        return

    if text and callback.message:
        with suppress(Exception):
            await callback.message.answer(text)


async def admin_click(callback: CallbackQuery) -> bool:
    """Кнопки, которые меняют подписки и рекламу, доступны только админам из ADMIN_IDS."""
    if is_admin(callback.from_user.id if callback.from_user else 0):
        return True

    await reply_to_click(callback, ADMIN_ONLY_CLICK)
    return False


def photo_source(value: str):
    """file_id, ссылка или файл рядом с ботом - что вставлено, то и отправляем."""
    with suppress(OSError, ValueError):
        if Path(value).is_file():
            return FSInputFile(value)
    return value


async def send_picture(bot, chat_id: int, photo: str, text: str, reply_markup=None):
    """Сообщение с картинкой. Картинка не вставлена или не отправилась - уходит один текст.

    Длинный текст не обрезаем: в подпись к фото у Telegram влезает 1024 символа, поэтому
    картинка уходит отдельным сообщением, а текст с кнопками - следом.
    """
    if not photo and not text:
        return None

    long_text = tg_len(text) > 1024
    if photo:
        try:
            sent = await bot.send_photo(
                chat_id=chat_id,
                photo=photo_source(photo),
                caption=None if long_text else (text or None),
                reply_markup=None if long_text else reply_markup,
            )
            if not long_text:
                return sent
        except Exception:
            pass        # неверный file_id не должен ломать сценарий - пишем текстом

    if not text:
        return None

    with suppress(Exception):
        return await bot.send_message(chat_id=chat_id, text=tg_cut(text, 4096), reply_markup=reply_markup)
    return None


def _touch_user(message: Message) -> None:
    """Регистрирует нового пользователя или обновляет last_seen. Без записи на диск."""
    if not message.from_user:
        return

    user_id = str(message.from_user.id)
    now = _now()
    stored = data['users'].get(user_id)
    if stored is not None:
        stored['last_seen'] = now
        stored['username'] = message.from_user.username or ''
        return

    src = message.from_user
    data['users'][user_id] = {
        'first_name': src.first_name or '',
        'last_name': src.last_name or '',
        'username': src.username or '',
        'joined_at': now,
        'last_seen': now,
    }
    commands = data['usage']['commands']
    commands['new_users'] = commands.get('new_users', 0) + 1


def increment_usage(category: str, name: str) -> None:
    bucket = data['usage'].setdefault(category, {})
    bucket[name] = bucket.get(name, 0) + 1
    save_data(data)


def track(message: Message, category: str, name: str) -> None:
    """Регистрация пользователя + счётчик за одну запись на диск."""
    _touch_user(message)
    increment_usage(category, name)


def format_top_counts(counts: dict[str, int]) -> str:
    if not counts:
        return 'Нет данных.'
    top = sorted(counts.items(), key=lambda item: item[1], reverse=True)[:10]
    return '\n'.join(f'{name}: {count}' for name, count in top)


def resolve_user_id(target: str) -> int | None:
    if not target:
        return None

    normalized = target.lstrip('@').strip()
    if normalized.isdigit():
        return int(normalized)

    for user_id, user_data in data['users'].items():
        if (user_data.get('username') or '').lstrip('@').lower() == normalized.lower():
            return int(user_id)

    return None


def get_admin_stats_text() -> str:
    usage = data['usage']
    blocks = '\n\n'.join(
        f'📊 Статистика {label}:\n{format_top_counts(usage.get(key, {}))}'
        for key, label in (('buttons', 'кнопок'), ('commands', 'команд'), ('functions', 'функций'))
    )
    published = sum(1 for post in data['posts'].values() if post.get('status') == 'published')
    active = active_subs()
    basic = sum(1 for _, stored in active if (stored.get('tier') or '') == 'basic')
    waiting = sum(1 for request in data['sub_requests'].values() if request.get('status') == 'pending')
    return (
        '🔐 Админ панель\n'
        f'Всего пользователей: {len(data["users"])}\n'
        f'Всего рассылок: {len(data.get("broadcasts", []))}\n'
        f'Опубликовано работ: {published}\n'
        f'Активных подписок: {len(active)} (базовых {basic}, продвинутых {len(active) - basic})\n'
        f'Заявок на оплату в ожидании: {waiting}\n'
        f'Рекламных цитат: {len(data["ads"])}\n\n'
        f'{blocks}'
    )


async def send_to_user(message: Message, target: str, content: str) -> None:
    """Общая часть /message_user и одноимённой кнопки: найти адресата, написать, включить пересылку."""
    target_id = resolve_user_id(target)
    if target_id is None:
        await message.answer(USER_NOT_FOUND)
        return

    try:
        await message.bot.send_message(chat_id=target_id, text=content)
        forwarding_sessions[target_id] = message.from_user.id if message.from_user else 0
        increment_usage('functions', 'message_user')
        await message.answer(
            f'Сообщение отправлено пользователю {target}.\n{FORWARDING_ENABLED}',
            reply_markup=admin_keyboard(),
        )
    except Exception:
        await message.answer(SEND_FAILED, reply_markup=admin_keyboard())


# подписки


def sub_of(user_id) -> dict | None:
    """Действующая подписка или None. Просроченные записи не удаляем - их разбирает наблюдатель."""
    stored = data['subs'].get(str(user_id))
    if not stored:
        return None

    until = str(stored.get('until') or '')
    return stored if until > _now() else None


def sub_tier(user_id) -> str:
    """'basic', 'pro' или пустая строка, если подписки нет."""
    tier = (sub_of(user_id) or {}).get('tier') or ''
    return tier if tier in SUB_TIERS else ''


def sub_badge(user_id) -> str:
    """Префикс над постом: у базовой фиксированный, у продвинутой свой (пока не выбран - стандартный)."""
    tier = sub_tier(user_id)
    if not tier:
        return ''

    own = (sub_of(user_id) or {}).get('prefix') or ''
    badge = own if tier == 'pro' and own else SUB_TIERS[tier]['badge']
    return f'{SUB_TIERS[tier]["icon"]} {badge}'


def until_label(stored: dict) -> str:
    """Дата окончания подписки в виде ДД.ММ.ГГГГ."""
    raw = str((stored or {}).get('until') or '')
    return f'{raw[8:10]}.{raw[5:7]}.{raw[0:4]}' if len(raw) >= 10 else '??.??.????'


def active_subs() -> list[tuple[str, dict]]:
    """Действующие подписки, ближайшие к окончанию - первыми."""
    found = [(user_id, stored) for user_id, stored in data['subs'].items() if sub_of(user_id)]
    found.sort(key=lambda item: str(item[1].get('until') or ''))
    return found


def grant_sub(user_id, tier: str) -> dict:
    """Включает подписку на SUB_DAYS дней. Остаток прежней не сгорает - новый срок идёт от него."""
    key = str(user_id)
    stored = data['subs'].get(key) or {}
    start = _utcnow()
    with suppress(ValueError, TypeError):
        start = max(start, datetime.fromisoformat(str(stored.get('until') or '').rstrip('Z')))

    fresh = {
        'tier': tier,
        'until': _iso(start + timedelta(days=SUB_DAYS)),
        'granted_at': _now(),
        'warned': False,             # предупреждение за SUB_WARN_DAYS дня уже отправлено
        'expired_notified': False,   # сообщение «подписка закончилась» уже отправлено
        'prefix': stored.get('prefix', ''),
        'prefix_pending': '',
    }
    data['subs'][key] = fresh
    return fresh


def pending_request(user_id) -> str:
    """id заявки на оплату, которая ещё висит без ответа. Пустая строка - заявок нет."""
    for request_id, request in data['sub_requests'].items():
        if str(request.get('user_id')) == str(user_id) and request.get('status') == 'pending':
            return request_id
    return ''


def sub_menu_text(user_id) -> str:
    stored = sub_of(user_id)
    if stored:
        tier = sub_tier(user_id)
        head = (f'💎 Твоя подписка: «{SUB_TIERS[tier]["title"]}» до {until_label(stored)}\n'
                f'Префикс: {sub_badge(user_id)}\n\n')
    else:
        head = '💎 Подписки для котиков ✨\n\n'

    return f'{head}{SUB_PERKS["basic"]}\n\n{SUB_PERKS["pro"]}\n\n{SUB_MENU_TAIL}'


def pay_text(tier: str) -> str:
    tier_data = SUB_TIERS[tier]
    return (f'{tier_data["icon"]} Оплата подписки «{tier_data["title"]}»\n'
            f'Сумма: {tier_data["price"]}\n'
            f'Срок: {SUB_DAYS} дней\n\n'
            f'{PAYMENT_DETAILS}\n\n'
            'После перевода нажми «✅ Оплатил» - заявка уйдёт админу на проверку 💖')


def sub_request_text(request_id: str, request: dict) -> str:
    tier_data = SUB_TIERS[request.get('tier') or 'basic']
    return ('💎 Заявка на подписку\n'
            f'Заявка №{request_id}\n'
            f'Пользователь: {author_label(request["user_id"])}\n'
            f'ID: {request["user_id"]}\n'
            f'Уровень: {tier_data["title"]} - {tier_data["price"]}\n\n'
            'Проверь перевод и решай кнопками ниже.')


def sub_granted_text(tier: str, stored: dict) -> str:
    tail = ('\n\nСвой префикс выбирается в меню подписки - кнопка «✏️ Сменить префикс» ✨'
            if tier == 'pro' else '')
    return (f'{SUB_TIERS[tier]["icon"]} Подписка «{SUB_TIERS[tier]["title"]}» включена '
            f'до {until_label(stored)}!\n\n{SUB_PERKS[tier]}{tail}')


def prefix_problem(wanted: str) -> str:
    """Пустая строка - префикс годится. Иначе текст, который надо показать человеку."""
    if not wanted:
        return 'Префикс не может быть пустым. Напиши текст или отмени через /cancel'
    if tg_len(wanted) > PREFIX_LIMIT:
        return (f'Слишком длинно: {tg_len(wanted)} символов, а можно до {PREFIX_LIMIT}. '
                'Сократи и пришли ещё раз 💖')

    lowered = wanted.lower()
    if '@' in wanted or 'http' in lowered or 't.me' in lowered:
        return 'Ссылки и упоминания в префиксе нельзя - придумай что-то другое ✨'
    return ''


# рекламные цитаты


def pick_ad() -> str:
    """Случайная цитата под пост. Список пуст - просто ничего не дописываем."""
    ads = [str(text).strip() for text in data['ads'] if str(text).strip()]
    return random.choice(ads) if ads else ''


def ads_text() -> str:
    if not data['ads']:
        return ('📢 Рекламных цитат нет - под постами без подписки ничего не дописывается.\n'
                'Добавь первую кнопкой ниже.')

    lines = '\n\n'.join(f'{i + 1}. {text}' for i, text in enumerate(data['ads']))
    return tg_cut('📢 Рекламные цитаты. Под постом человека без подписки бот дописывает '
                  f'одну из них случайно.\n\n{lines}', 3800)


def add_ad(text: str) -> str:
    """Добавляет цитату. Возвращает текст ошибки или пустую строку, если всё хорошо."""
    wanted = ' '.join(text.split())
    if not wanted:
        return 'Текст не может быть пустым.'
    if tg_len(wanted) > AD_LIMIT:
        return (f'Слишком длинно: {tg_len(wanted)} символов, а под постом влезает {AD_LIMIT}. '
                'Сократи и пришли ещё раз.')
    if wanted in data['ads']:
        return 'Такая цитата уже есть.'

    data['ads'].append(wanted)
    increment_usage('functions', 'ad_add')      # save_data здесь же сохраняет и цитату
    return ''


# работы пользователя


def author_username(user_id: int) -> str:
    return (data['users'].get(str(user_id), {}).get('username') or '').lstrip('@')


def author_label(user_id: int) -> str:
    username = author_username(user_id)
    return f'@{username}' if username else f'ID {user_id}'


def author_url(user_id: int) -> str:
    """Ссылка на автора для кнопки под постом. Без username остаётся ссылка по id."""
    username = author_username(user_id)
    return f'https://t.me/{username}' if username else f'tg://user?id={user_id}'


def find_post(callback: CallbackQuery) -> tuple[str, dict | None]:
    """Работа по callback_data. Формат везде одинаковый: действие:id[:параметр]."""
    parts = (callback.data or '').split(':')
    post_id = parts[1] if len(parts) > 1 else ''
    return post_id, data['posts'].get(post_id)


def own_post(callback: CallbackQuery) -> tuple[str, dict | None]:
    """Работа из callback_data, если её автор - тот, кто нажал кнопку."""
    post_id, post = find_post(callback)
    if post is None or post.get('user_id') != callback.from_user.id:
        return post_id, None
    return post_id, post


def published_posts(user_id: int) -> list[tuple[str, dict]]:
    found = [(post_id, post) for post_id, post in data['posts'].items()
             if post.get('user_id') == user_id and post.get('status') == 'published']
    found.sort(key=lambda item: int(item[0]), reverse=True)
    return found[:PROFILE_WORKS]


def work_label(post: dict) -> str:
    """Подпись кнопки в профиле: ДД.ММ и начало описания."""
    created = post.get('created_at') or ''
    date = f'{created[8:10]}.{created[5:7]}' if len(created) >= 10 else '??.??'
    head = ' '.join((post.get('caption') or 'без описания').split())[:28]
    return f'{"✅" if post.get("actual", True) else "❌"} {date} · {head}'


def work_caption(post: dict) -> str:
    status = 'актуально ✅' if post.get('actual', True) else 'неактуально ❌'
    return f'{tg_cut(post.get("caption") or "Без описания", CAPTION_LIMIT)}\n\nСтатус: {status}'


def reminder_left(post: dict) -> str:
    """Сколько ещё ждать до следующей напоминалки. Пустая строка - можно отправлять."""
    last = post.get('last_reminder_at')
    if not last:
        return ''

    with suppress(ValueError, TypeError):
        left = REMINDER_COOLDOWN - (_utcnow() - datetime.fromisoformat(str(last).rstrip('Z')))
        if left.total_seconds() > 0:
            hours, minutes = divmod(int(left.total_seconds()) // 60, 60)
            return f'{hours} ч {minutes} мин'
    return ''


def apply_perks(post: dict) -> None:
    """Снимок плюшек на момент публикации: подписка кончится, а пост останется таким, каким вышел."""
    tier = sub_tier(post.get('user_id') or 0)
    post['tier'] = tier
    post['badge'] = sub_badge(post.get('user_id') or 0)
    post['tag'] = SUB_TIERS[tier]['tag'] if tier else ''
    post['ad'] = '' if tier else pick_ad()


def channel_caption(post: dict) -> str:
    """Подпись поста в канале: префикс, описание, хештег и рекламная цитата.

    Отправляется с parse_mode='HTML', поэтому текст человека обязательно экранируем -
    иначе случайная угловая скобка в описании уронит публикацию.
    """
    parts = []
    if post.get('badge'):
        parts.append(f'<b>{html.escape(post["badge"])}</b>')

    parts.append(html.escape(tg_cut(post.get('caption') or '', CAPTION_LIMIT)))
    if post.get('tag'):
        parts.append(html.escape(post['tag']))
    if post.get('ad'):
        parts.append(f'<blockquote>{html.escape(tg_cut(post["ad"], AD_LIMIT))}</blockquote>')

    return '\n\n'.join(part for part in parts if part)


def moderation_prefix(post: dict) -> str:
    """Шапка карточки на модерации: префикс автора, его приоритет и просьба о закрепе."""
    lines = [line for line in (post.get('badge') or '',
                               SUB_TIERS[post['tier']]['priority'] if post.get('tier') in SUB_TIERS else '',
                               '📌 Автор просит закрепить пост' if post.get('pin') else '') if line]
    return '\n'.join(lines) + '\n\n' if lines else ''


async def send_to_moderation(bot, post_id: str, post: dict, prefix: str = '') -> int | None:
    """Отправляет работу в чат модерации. Возвращает id сообщения или None, если не вышло."""
    try:
        sent = await bot.send_photo(
            chat_id=PUBLISH_CHAT_ID,
            photo=post['photo'],
            caption=tg_cut(f'{prefix}{moderation_prefix(post)}{post.get("caption") or ""}', 1024) or None,
            reply_markup=acetp_keyboard(post_id),
        )
    except Exception:
        return None

    with suppress(Exception):
        await bot.send_message(
            chat_id=PUBLISH_CHAT_ID,
            text=f'Пользователь: {author_label(post["user_id"])}\nID: {post["user_id"]}',
        )
    return sent.message_id


async def refresh_channel_post(bot, post: dict) -> bool:
    """Обновляет клавиатуру опубликованного поста под текущий статус работы."""
    message_id = post.get('channel_message_id')
    if not message_id:
        return False

    try:
        await bot.edit_message_reply_markup(
            chat_id=PUBLISH_CHANNEL_ID,
            message_id=message_id,
            reply_markup=post_keyboard(post.get('actual', True), author_url(post['user_id'])),
        )
        return True
    except Exception:
        return False


async def react_to_post(bot, post: dict) -> None:
    """Реакция бота на опубликованный пост: 🔥 у базовой, 🏆 у продвинутой."""
    emoji = SUB_TIERS.get(post.get('tier') or '', {}).get('reaction', '')
    if not emoji or not post.get('channel_message_id'):
        return

    with suppress(Exception):
        await bot.set_message_reaction(
            chat_id=PUBLISH_CHANNEL_ID,
            message_id=post['channel_message_id'],
            reaction=[ReactionTypeEmoji(emoji=emoji)],
        )


async def pin_if_asked(bot, post: dict) -> None:
    """Закрепляет пост, если автор просил и подписка на момент публикации была.

    Закрепы копятся, поэтому каждый запоминаем: наблюдатель снимет его через PIN_HOURS часов.
    """
    message_id = post.get('channel_message_id')
    if not post.get('pin') or not post.get('tier') or not message_id:
        return

    try:
        await bot.pin_chat_message(chat_id=PUBLISH_CHANNEL_ID, message_id=message_id,
                                   disable_notification=True)
    except Exception:
        return      # нет права закреплять - пост всё равно опубликован, ничего не ломаем

    data['pins'].append({'message_id': message_id, 'pinned_at': _now(), 'tries': 0})
    increment_usage('functions', 'pin_post')     # save_data здесь же сохраняет и закреп


# наблюдатель: подписки и закрепы


async def check_subscriptions(bot) -> None:
    """Предупреждает за SUB_WARN_DAYS дня и сообщает, когда подписка закончилась."""
    now = _now()
    soon = _iso(_utcnow() + timedelta(days=SUB_WARN_DAYS))
    changed = False

    for user_id, stored in list(data['subs'].items()):
        until = str(stored.get('until') or '')
        if not until:
            continue

        if until <= now:
            if not stored.get('expired_notified'):
                stored['expired_notified'] = True
                changed = True
                tier_data = SUB_TIERS.get(stored.get('tier') or 'basic', SUB_TIERS['basic'])
                with suppress(Exception):
                    await bot.send_message(
                        chat_id=int(user_id),
                        text=(f'💔 Подписка «{tier_data["title"]}» закончилась.\n'
                              'На новых постах пропадут префикс и хештег, а снизу снова будет '
                              f'рекламная цитата. Продлить - кнопка «{SUB_BUTTON}» в главном меню ✨'),
                        reply_markup=main_keyboard(),
                    )
            continue

        if until <= soon and not stored.get('warned'):
            stored['warned'] = True
            changed = True
            tier_data = SUB_TIERS.get(stored.get('tier') or 'basic', SUB_TIERS['basic'])
            with suppress(Exception):
                await bot.send_message(
                    chat_id=int(user_id),
                    text=(f'⏳ Подписка «{tier_data["title"]}» заканчивается {until_label(stored)} - '
                          f'осталось меньше {SUB_WARN_DAYS} дней.\n'
                          f'Продлить можно кнопкой «{SUB_BUTTON}» в главном меню 💖'),
                    reply_markup=main_keyboard(),
                )

    if changed:
        save_data(data)


async def drop_old_pins(bot) -> None:
    """Снимает закрепы старше PIN_HOURS часов."""
    limit = _iso(_utcnow() - timedelta(hours=PIN_HOURS))
    keep: list[dict] = []
    changed = False

    for item in list(data['pins']):
        if str(item.get('pinned_at') or '') > limit:
            keep.append(item)
            continue

        changed = True
        try:
            await bot.unpin_chat_message(chat_id=PUBLISH_CHANNEL_ID, message_id=item.get('message_id'))
        except Exception:
            # Telegram мог просто не ответить - пробуем ещё пару раз и забываем,
            # иначе удалённый пост остался бы в списке навсегда.
            item['tries'] = int(item.get('tries') or 0) + 1
            if item['tries'] < PIN_TRIES:
                keep.append(item)

    if changed:
        data['pins'] = keep
        save_data(data)


async def subscription_watcher(bot) -> None:
    """Фоновая задача: раз в SUB_CHECK_PERIOD проверяет подписки и снимает старые закрепы.

    Запускается из main.py. Отдельного планировщика в боте нет, и это к лучшему: после рестарта
    проверка просто случится сразу, а не потеряется.
    """
    while True:
        with suppress(Exception):
            await check_subscriptions(bot)
        with suppress(Exception):
            await drop_old_pins(bot)
        await asyncio.sleep(SUB_CHECK_PERIOD)


@user.message(CommandStart())
async def cmd_start(message: Message):
    track(message, 'commands', 'start')
    await message.answer('🐾 Приветик от ботика. У нас бесплатная выкладка ваших тейков! 💖',
                         reply_markup=main_keyboard())


@user.message(F.text == '🔙 Назад ✨')
async def cmd_back(message: Message, state: FSMContext):
    await state.clear()
    await cmd_start(message)


@user.message(F.text == '📞 Прямая связь 💖')
async def cmd_direct_link(message: Message):
    track(message, 'buttons', 'прямая связь')
    await message.answer('📩 Личка админа: @toymaaa 💖',
                         reply_markup=move_nazad())


@user.message(F.text == '📜 Правила ✨')
async def cmd_rules(message: Message):
    track(message, 'buttons', 'правила')
    await message.answer(
        "📜 Основные правила выкладки артов: ✨\n\n"
        "1️⃣ Разрешено: адопты любых видов, а также комишки 🎨\n\n"
        "📌 1.1 Посты\n"
        "- Арты не вашего авторства, посредничество, принты без разрешения.\n"
        "- Мейкеры.\n\n"
        "💰 1.2 Ставки\n"
        "- Нельзя удалять или менять ставки.\n"
        "- AUTO перебивается только AUTO2/AUTO3.\n"
        "- Игнор >24ч без ответа - ставка аннулируется.\n\n"
        "💬 1.3 Оскорбления\n"
        "- Запрещены в любом виде.\n\n"
        "📢 1.4 Оффтоп\n"
        "- Посты не по теме адоптов.\n\n"
        "🤖 1.5 ИИ\n"
        "- Полностью запрещён.",
        reply_markup=move_nazad()
    )


@user.message(F.text == '👤 Профиль ✨')
async def cmd_profile(message: Message, state: FSMContext):
    track(message, 'buttons', 'профиль')
    await state.clear()
    if not message.from_user:
        return

    posts = published_posts(message.from_user.id)
    if not posts:
        await message.answer(PROFILE_EMPTY, reply_markup=move_nazad())
        return

    await message.answer(PROFILE_HEADER,
                         reply_markup=works_keyboard([(post_id, work_label(post)) for post_id, post in posts]))


@user.message(F.text == SUB_BUTTON)
async def cmd_subscription(message: Message, state: FSMContext):
    """Экран подписок: картинка, что даёт каждый уровень, и кнопки выбора."""
    track(message, 'buttons', 'подписка')
    await state.clear()
    if not message.from_user:
        return

    await send_picture(message.bot, message.chat.id, SUB_PHOTO, sub_menu_text(message.from_user.id),
                       sub_menu_keyboard(sub_tier(message.from_user.id)))


@user.message(F.text == '🔙 Выйти')
async def cmd_admin_exit(message: Message, state: FSMContext):
    await state.clear()
    await message.answer('🐾 Главное меню 💖', reply_markup=main_keyboard())


@user.message(Command('cancel'), StateFilter(AdminBroadcast.waiting_text, AdminMessage.target,
                                            AdminMessage.text, AdminGroupMessage.waiting_text,
                                            AdminAd.waiting_text, SubPrefix.waiting_text))
async def cmd_cancel_broadcast(message: Message, state: FSMContext):
    current = await state.get_state()
    await state.clear()

    if current == SubPrefix.waiting_text.state:
        await message.answer('Отменено.', reply_markup=main_keyboard())
        return

    await message.answer(
        'Рассылка отменена.' if current == AdminBroadcast.waiting_text.state else 'Отменено.',
        reply_markup=admin_keyboard(),
    )


@user.message(Command('send_to_group'))
@admin_only('⚠️ У вас нет доступа к этой команде.')
async def cmd_send_to_group(message: Message):
    text = (message.text or message.caption or '')[len('/send_to_group'):].strip()
    if not text:
        await message.answer('Напишите текст после команды, например: /send_to_group Привет')
        return

    await message.bot.send_message(chat_id=PUBLISH_CHAT_ID, text=text)
    increment_usage('functions', 'send_to_group')
    await message.answer('Сообщение отправлено в группу')


@user.message(Command('admin'))
@admin_only('⚠️ У вас нет доступа к админ-панели.')
async def cmd_admin_panel(message: Message):
    track(message, 'commands', 'admin')
    await message.answer(
        '🔐 Админ-панель:\n'
        'Выберите действие кнопкой ниже или используйте команду:\n'
        '/admin_stats - посмотреть статистику\n'
        '/broadcast - отправить рассылку всем пользователям\n'
        '/message_user <id|@username> <текст> - написать пользователю\n'
        '/send_to_group <текст> - отправить сообщение в группу\n'
        '/ads - рекламные цитаты под постами\n'
        '/ads_add <текст> - добавить цитату\n'
        '/ads_del <номер> - удалить цитату\n'
        '/subs - кто с подпиской\n'
        '/sub_give <id|@username> <basic|pro> - выдать подписку руками\n'
        '/sub_take <id|@username> - снять подписку\n'
        '/cancel - отменить рассылку',
        reply_markup=admin_keyboard()
    )


@user.message(Command('admin_stats'))
@admin_only('⚠️ У вас нет доступа к статистике.')
async def cmd_admin_stats(message: Message):
    track(message, 'commands', 'admin_stats')
    await message.answer(get_admin_stats_text(), reply_markup=admin_keyboard())


@user.message(F.text == '📊 Статистика')
@admin_only()
async def cmd_admin_stats_button(message: Message):
    await cmd_admin_stats(message)


@user.message(F.text == '📣 Рассылка')
@admin_only()
async def cmd_broadcast_button(message: Message, state: FSMContext):
    await cmd_broadcast(message, state=state)


@user.message(F.text == '✉️ Написать пользователю')
@admin_only()
async def cmd_message_user_button(message: Message, state: FSMContext):
    await state.set_state(AdminMessage.target)
    await message.answer('Введите ID или @username пользователя, которому хотите написать.')


@user.message(F.text == '📤 В группу')
@admin_only()
async def cmd_group_message_button(message: Message, state: FSMContext):
    await state.set_state(AdminGroupMessage.waiting_text)
    await message.answer('Введите текст, который нужно отправить в группу.')


@user.message(Command('ads'))
@admin_only('⚠️ У вас нет доступа к этой команде.')
async def cmd_ads(message: Message):
    track(message, 'commands', 'ads')
    await message.answer(ads_text(), reply_markup=ads_keyboard(len(data['ads'])))


@user.message(F.text == '📢 Реклама')
@admin_only()
async def cmd_ads_button(message: Message):
    await cmd_ads(message)


@user.message(Command('ads_add'))
@admin_only('⚠️ У вас нет доступа к этой команде.')
async def cmd_ads_add(message: Message):
    text = (message.text or '')[len('/ads_add'):].strip()
    problem = add_ad(text)
    if problem:
        await message.answer(f'{problem}\nИспользование: /ads_add <текст цитаты>')
        return

    await message.answer('Цитата добавлена.', reply_markup=admin_keyboard())
    await message.answer(ads_text(), reply_markup=ads_keyboard(len(data['ads'])))


@user.message(Command('ads_del'))
@admin_only('⚠️ У вас нет доступа к этой команде.')
async def cmd_ads_del(message: Message):
    number = (message.text or '')[len('/ads_del'):].strip()
    if not number.isdigit() or not 1 <= int(number) <= len(data['ads']):
        await message.answer(f'Использование: /ads_del <номер от 1 до {len(data["ads"])}>')
        return

    data['ads'].pop(int(number) - 1)
    increment_usage('functions', 'ad_del')      # save_data здесь же сохраняет и список
    await message.answer(ads_text(), reply_markup=ads_keyboard(len(data['ads'])))


@user.message(Command('subs'))
@admin_only('⚠️ У вас нет доступа к этой команде.')
async def cmd_subs(message: Message):
    track(message, 'commands', 'subs')
    active = active_subs()
    if not active:
        await message.answer('💎 Активных подписок нет.', reply_markup=admin_keyboard())
        return

    lines = '\n'.join(
        f'{author_label(int(user_id))} - {SUB_TIERS[stored.get("tier") or "basic"]["title"]} '
        f'до {until_label(stored)}'
        for user_id, stored in active[:30] if str(user_id).isdigit()
    )
    await message.answer(f'💎 Активные подписки ({len(active)}):\n{lines}', reply_markup=admin_keyboard())


@user.message(F.text == '💎 Подписки')
@admin_only()
async def cmd_subs_button(message: Message):
    await cmd_subs(message)


@user.message(Command('sub_give'))
@admin_only('⚠️ У вас нет доступа к этой команде.')
async def cmd_sub_give(message: Message):
    parts = (message.text or '').split()
    tier = parts[2].lower() if len(parts) > 2 else ''
    target_id = resolve_user_id(parts[1]) if len(parts) > 1 else None
    if target_id is None or tier not in SUB_TIERS:
        await message.answer('Использование: /sub_give <id|@username> <basic|pro>')
        return

    stored = grant_sub(target_id, tier)
    increment_usage('functions', 'sub_give')    # save_data здесь же сохраняет и подписку
    await message.answer(f'Подписка «{SUB_TIERS[tier]["title"]}» выдана {author_label(target_id)} '
                         f'до {until_label(stored)}.', reply_markup=admin_keyboard())

    with suppress(Exception):
        await message.bot.send_message(chat_id=target_id, text=sub_granted_text(tier, stored),
                                       reply_markup=main_keyboard())


@user.message(Command('sub_take'))
@admin_only('⚠️ У вас нет доступа к этой команде.')
async def cmd_sub_take(message: Message):
    parts = (message.text or '').split()
    target_id = resolve_user_id(parts[1]) if len(parts) > 1 else None
    if target_id is None or str(target_id) not in data['subs']:
        await message.answer('Использование: /sub_take <id|@username> (у человека должна быть подписка)')
        return

    data['subs'].pop(str(target_id), None)
    increment_usage('functions', 'sub_take')    # save_data здесь же сохраняет и список подписок
    await message.answer(f'Подписка снята у {author_label(target_id)}.', reply_markup=admin_keyboard())


@user.message(StateFilter(AdminMessage.target))
@admin_only()
async def cmd_message_user_target(message: Message, state: FSMContext):
    target = (message.text or '').strip()
    if not target:
        await message.answer('Нужен текст: пришлите ID или @username пользователя.')
        return

    await state.update_data(target=target)
    await state.set_state(AdminMessage.text)
    await message.answer('Введите текст сообщения для пользователя.')


@user.message(StateFilter(AdminMessage.text))
@admin_only()
async def cmd_message_user_text(message: Message, state: FSMContext):
    target = (await state.get_data()).get('target', '')
    content = (message.text or '').strip()
    if not target or not content:
        await message.answer('Пожалуйста, укажите ID или @username и текст сообщения.')
        return

    try:
        await send_to_user(message, target, content)
    finally:
        await state.clear()


@user.message(StateFilter(AdminGroupMessage.waiting_text))
@admin_only()
async def cmd_group_message_text(message: Message, state: FSMContext):
    text = (message.text or '').strip()
    if not text:
        await message.answer('Текст не может быть пустым. Введите сообщение для группы.')
        return

    try:
        await message.bot.send_message(chat_id=PUBLISH_CHAT_ID, text=text)
        increment_usage('functions', 'send_to_group')
        await message.answer('Сообщение отправлено в группу.', reply_markup=admin_keyboard())
    except Exception:
        await message.answer('Не удалось отправить сообщение в группу.')
    finally:
        await state.clear()


@user.message(StateFilter(AdminAd.waiting_text))
@admin_only()
async def cmd_ad_text(message: Message, state: FSMContext):
    problem = add_ad((message.text or '').strip())
    if problem:
        await message.answer(f'{problem}\nПришли текст ещё раз или отмени через /cancel')
        return

    await state.clear()
    await message.answer('Цитата добавлена.', reply_markup=admin_keyboard())
    await message.answer(ads_text(), reply_markup=ads_keyboard(len(data['ads'])))


@user.message(Command('message_user'))
@admin_only('⚠️ У вас нет доступа к этой команде.')
async def cmd_message_user(message: Message):
    parts = (message.text or '').split(maxsplit=2)
    if len(parts) < 3:
        await message.answer('Использование: /message_user <id|@username> <текст>')
        return

    content = parts[2].strip()
    if not content:
        await message.answer('Текст сообщения не может быть пустым.')
        return

    await send_to_user(message, parts[1], content)


@user.message(Command('broadcast'))
@admin_only('⚠️ У вас нет доступа к рассылке.')
async def cmd_broadcast(message: Message, state: FSMContext):
    await state.set_state(AdminBroadcast.waiting_text)
    await message.answer('Напишите текст для рассылки всем зарегистрированным пользователям.')


@user.message(F.text, StateFilter(AdminBroadcast.waiting_text))
@admin_only('⚠️ У вас нет доступа к рассылке.')
async def cmd_send_broadcast(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text:
        await message.answer('Текст не может быть пустым. Пожалуйста, введите текст для рассылки.')
        return

    sent = failed = 0
    for user_id in [int(stored_id) for stored_id in data['users']]:
        try:
            await message.bot.send_message(chat_id=user_id, text=text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(BROADCAST_PAUSE)

    data['broadcasts'].append({
        'text': text,
        'sent_at': _now(),
        'sent': sent,
        'failed': failed,
    })
    await state.clear()
    increment_usage('functions', 'broadcast')  # save_data здесь же сохраняет и broadcasts
    await message.answer(f'Рассылка отправлена: {sent} пользователям, {failed} не удалось.', reply_markup=admin_keyboard())


# создание анкеты

@user.message(F.text == '📝 Анкета 💖')
async def cmd_anket_start(message: Message, state: FSMContext):
    track(message, 'buttons', 'анкета')
    await state.set_state(anket.photo)
    await message.answer(ANKET_PHOTO_PROMPT, reply_markup=ReplyKeyboardRemove())


@user.message(F.text == '🔄 Переделать анкету ✨')
async def cmd_anket_restart(message: Message, state: FSMContext):
    track(message, 'buttons', 'переделать анкету')
    await state.clear()
    await state.set_state(anket.photo)
    await message.answer(ANKET_PHOTO_PROMPT, reply_markup=ReplyKeyboardRemove())


@user.message(~F.photo, StateFilter(anket.photo))
async def cmd_anket_not_photo(message: Message):
    await message.answer('⚠️ Пожалуйста, пришлите фото, а не текст или другой тип сообщения 💖')


@user.message(F.photo, StateFilter(anket.photo))
async def cmd_anket_photo(message: Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await state.set_state(anket.info)
    await message.answer('📩 Отправьте сюда свою информацию о арте либо что угодно другое, а также цену и свой контакт 💖')


@user.message(F.text.in_(PIN_LABELS), StateFilter(anket.info))
async def cmd_anket_pin(message: Message, state: FSMContext):
    """Переключатель «закреплять или нет». Кнопка есть только у подписчиков."""
    if not message.from_user or not sub_tier(message.from_user.id):
        await message.answer('📌 Закреп поста - плюшка подписки. Загляни в «💎 Подписка ✨» ✨')
        return

    wanted = not (await state.get_data()).get('pin')
    await state.update_data(pin=wanted)
    increment_usage('functions', 'pin_choice')
    await message.answer('📌 Пост закрепим после одобрения ✨' if wanted else '📌 Закреплять не будем',
                         reply_markup=accetp_keyboard(wanted))


@user.message(F.text == '✅ Верно 💖', StateFilter(anket.info))
async def cmd_confirm_anket(message: Message, state: FSMContext):
    track(message, 'functions', 'confirm_anket')
    form = await state.get_data()
    user_id = message.from_user.id if message.from_user else 0
    tier = sub_tier(user_id)
    post_id = str(data['next_post_id'])
    post = {
        'user_id': user_id,
        'photo': form.get('photo'),
        'caption': form.get('info'),
        'created_at': _now(),
        'status': 'pending',            # pending | published | rejected
        'actual': True,
        'awaiting': True,               # ждёт решения администратора
        'moderation_message_id': None,
        'channel_message_id': None,
        'last_reminder_at': None,
        'tier': tier,                   # плюшки пересчитаются при публикации, см. apply_perks
        'badge': sub_badge(user_id),
        'tag': SUB_TIERS[tier]['tag'] if tier else '',
        'ad': '',
        'pin': bool(form.get('pin')),
    }

    moderation_message_id = await send_to_moderation(message.bot, post_id, post)
    if moderation_message_id is None:
        # состояние не сбрасываем: можно просто нажать «✅ Верно 💖» ещё раз
        await message.answer('⚠️ Не получилось отправить анкету на модерацию. '
                             'Попробуй нажать «✅ Верно 💖» ещё раз через минутку 💖')
        return

    post['moderation_message_id'] = moderation_message_id
    data['posts'][post_id] = post
    data['next_post_id'] = int(post_id) + 1
    save_data(data)

    if not tier:
        await message.answer('📋 Ваша анкета создана, ждите одобрение от администратора ✨', reply_markup=move_nazad())
        # сообщение-заглушка: текст и картинку меняй в WAIT_TEXT и WAIT_PHOTO наверху файла
        await send_picture(message.bot, message.chat.id, WAIT_PHOTO, WAIT_TEXT)
    await state.clear()


@user.message(F.text, StateFilter(anket.info))
async def cmd_fullanket(message: Message, state: FSMContext):
    if message.text in {'Верно', 'Переделать анкету'} or message.text in PIN_LABELS:
        return

    # подпись к фото у Telegram ограничена 1024 символами, дальше не влезет ни предпросмотр, ни пост
    if tg_len(message.text) > CAPTION_LIMIT:
        await message.answer(f'⚠️ Описание слишком длинное: {tg_len(message.text)} символов, '
                             f'а под фото влезает {CAPTION_LIMIT}. Сократи немного и пришли ещё раз 💖')
        return

    track(message, 'functions', 'fill_anket_info')
    await state.update_data(info=message.text)
    form = await state.get_data()

    await message.answer_photo(
        photo=form.get('photo'),
        caption=f"{form.get('info')}\n",
        reply_markup=ReplyKeyboardRemove(),
    )

    # кнопку закрепа показываем только подписчикам - у остальных клавиатура как была
    has_sub = bool(message.from_user and sub_tier(message.from_user.id))
    await message.answer('❓ Всё верно? 💖',
                         reply_markup=accetp_keyboard(bool(form.get('pin')) if has_sub else None))


# модерация

async def moderate_post(callback: CallbackQuery, action: str) -> None:
    """Общая часть approve/reject: опубликовать, ответить админу, уведомить автора, отметить пост реакцией."""
    notice, emoji, mark, done = MODERATION[action]
    _, post = find_post(callback)
    if post is None or not post.get('awaiting'):
        await reply_to_click(callback, 'Пост уже обработан')
        return

    if action == 'approve':
        apply_perks(post)       # префикс, хештег и реклама - по подписке на момент публикации
        try:
            published = await callback.bot.send_photo(
                chat_id=PUBLISH_CHANNEL_ID,
                photo=post['photo'],
                caption=channel_caption(post),
                parse_mode='HTML',
                reply_markup=post_keyboard(post.get('actual', True), author_url(post['user_id'])),
            )
        except Exception:
            # ничего не помечаем - кнопки остаются, можно нажать ещё раз
            await reply_to_click(callback, 'Не удалось опубликовать пост в канале. '
                                           'Проверь права бота и попробуй ещё раз.')
            return
        post['channel_message_id'] = published.message_id
        post['status'] = 'published'
    elif post.get('status') != 'published':
        post['status'] = 'rejected'     # отказ по напоминалке уже опубликованный пост не снимает

    post['awaiting'] = False
    increment_usage('functions', f'{action}_post')   # save_data здесь же сохраняет и работу

    # решение записано - отвечаем сразу, дальше ещё несколько запросов, и окно ответа успело бы истечь
    await reply_to_click(callback, done, alert=False)

    if action == 'approve':
        await react_to_post(callback.bot, post)
        await pin_if_asked(callback.bot, post)

    with suppress(Exception):
        await callback.bot.send_message(chat_id=post['user_id'], text=notice, reply_markup=move_nazad())

    with suppress(Exception):
        await callback.message.edit_reply_markup(reply_markup=None)

    try:
        await callback.message.bot.set_message_reaction(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            reaction=[ReactionTypeEmoji(emoji=emoji)],
        )
    except Exception:
        with suppress(Exception):
            await callback.message.edit_caption((callback.message.caption or '') + f'\n\n{mark}')


@user.callback_query(F.data.startswith('approve:'))
async def approve_post(callback: CallbackQuery):
    await moderate_post(callback, 'approve')


@user.callback_query(F.data.startswith('reject:'))
async def reject_post(callback: CallbackQuery):
    await moderate_post(callback, 'reject')


# подписки: выбор, оплата, проверка админом

@user.callback_query(F.data == 'sub:menu')
async def cb_sub_menu(callback: CallbackQuery):
    """Кнопка «Назад» с экрана оплаты: возвращаемся к выбору подписки."""
    await reply_to_click(callback)
    if callback.message:
        with suppress(Exception):
            await callback.message.delete()

    await send_picture(callback.bot, callback.from_user.id, SUB_PHOTO,
                       sub_menu_text(callback.from_user.id),
                       sub_menu_keyboard(sub_tier(callback.from_user.id)))


@user.callback_query(F.data == 'sub:close')
async def cb_sub_close(callback: CallbackQuery):
    await reply_to_click(callback)
    if not callback.message:
        return

    with suppress(Exception):
        await callback.message.delete()

    with suppress(Exception):
        await callback.message.answer('🐾 Главное меню 💖', reply_markup=main_keyboard())


@user.callback_query(F.data.startswith('sub:buy:'))
async def cb_sub_buy(callback: CallbackQuery):
    """Экран оплаты: та же картинка, цена выбранного уровня и реквизиты."""
    tier = (callback.data or '').split(':')[-1]
    if tier not in SUB_TIERS:
        await reply_to_click(callback, 'Такого уровня подписки нет')
        return

    await reply_to_click(callback)
    increment_usage('functions', f'sub_open_{tier}')
    if callback.message:
        with suppress(Exception):
            await callback.message.delete()

    await send_picture(callback.bot, callback.from_user.id, PAY_PHOTO, pay_text(tier), pay_keyboard(tier))


@user.callback_query(F.data.startswith('sub:paid:'))
async def cb_sub_paid(callback: CallbackQuery):
    """«Оплатил»: заявка уходит в админский чат, там её одобряют или отклоняют."""
    tier = (callback.data or '').split(':')[-1]
    if tier not in SUB_TIERS:
        await reply_to_click(callback, 'Такого уровня подписки нет')
        return

    if pending_request(callback.from_user.id):
        await reply_to_click(callback, SUB_REQUEST_DOUBLE)
        return

    # отвечаем сразу, а результат пишем сообщением: отправка админу может занять пару секунд,
    # и окно ответа на нажатие успело бы закрыться
    await reply_to_click(callback)

    request_id = str(data['next_sub_request_id'])
    request = {
        'user_id': callback.from_user.id,
        'tier': tier,
        'created_at': _now(),
        'status': 'pending',        # pending | approved | rejected
    }
    data['sub_requests'][request_id] = request
    data['next_sub_request_id'] = int(request_id) + 1
    increment_usage('functions', 'sub_request')      # save_data здесь же сохраняет и заявку

    try:
        await callback.bot.send_message(chat_id=PUBLISH_CHAT_ID,
                                        text=sub_request_text(request_id, request),
                                        reply_markup=sub_request_keyboard(request_id))
    except Exception:
        # заявку не показали админу - снимаем её, иначе человек не сможет отправить новую
        data['sub_requests'].pop(request_id, None)
        save_data(data)
        if callback.message:
            with suppress(Exception):
                await callback.message.answer(SUB_REQUEST_FAILED)
        return

    if callback.message:
        with suppress(Exception):
            await callback.message.edit_reply_markup(reply_markup=None)

        with suppress(Exception):
            await callback.message.answer(SUB_REQUEST_SENT, reply_markup=move_nazad())


async def moderate_sub(callback: CallbackQuery, approve: bool) -> None:
    """Общая часть одобрения и отказа по оплате."""
    if not await admin_click(callback):
        return

    parts = (callback.data or '').split(':')
    request = data['sub_requests'].get(parts[1] if len(parts) > 1 else '')
    if request is None or request.get('status') != 'pending':
        await reply_to_click(callback, 'Заявка уже обработана')
        return

    tier = request.get('tier') if request.get('tier') in SUB_TIERS else 'basic'
    request['status'] = 'approved' if approve else 'rejected'
    request['closed_at'] = _now()
    request['closed_by'] = callback.from_user.id
    stored = grant_sub(request['user_id'], tier) if approve else {}
    increment_usage('functions', 'sub_approve' if approve else 'sub_reject')

    await reply_to_click(callback, 'Подписка выдана' if approve else 'Заявка отклонена', alert=False)

    if callback.message:
        mark = f'✅ Подписка выдана до {until_label(stored)}' if approve else '❌ Отклонено'
        with suppress(Exception):
            await callback.message.edit_text(f'{callback.message.text or ""}\n\n{mark}', reply_markup=None)

    with suppress(Exception):
        await callback.bot.send_message(
            chat_id=request['user_id'],
            text=sub_granted_text(tier, stored) if approve else SUB_REJECTED,
            reply_markup=main_keyboard(),
        )


@user.callback_query(F.data.startswith('subok:'))
async def cb_sub_approve(callback: CallbackQuery):
    await moderate_sub(callback, True)


@user.callback_query(F.data.startswith('subno:'))
async def cb_sub_reject(callback: CallbackQuery):
    await moderate_sub(callback, False)


@user.callback_query(F.data == 'sub:prefix')
async def cb_sub_prefix(callback: CallbackQuery, state: FSMContext):
    """Свой префикс у продвинутой подписки: человек пишет текст, дальше его смотрит админ."""
    stored = sub_of(callback.from_user.id)
    if not stored or sub_tier(callback.from_user.id) != 'pro':
        await reply_to_click(callback, PREFIX_ONLY_PRO)
        return

    if stored.get('prefix_pending'):
        await reply_to_click(callback, 'Префикс уже ждёт проверки админом 💖')
        return

    await reply_to_click(callback)
    await state.set_state(SubPrefix.waiting_text)
    if callback.message:
        with suppress(Exception):
            await callback.message.answer(PREFIX_PROMPT, reply_markup=move_nazad())


async def moderate_prefix(callback: CallbackQuery, approve: bool) -> None:
    """Общая часть разрешения и отказа по своему префиксу."""
    if not await admin_click(callback):
        return

    parts = (callback.data or '').split(':')
    stored = data['subs'].get(parts[1] if len(parts) > 1 else '')
    wanted = (stored or {}).get('prefix_pending') or ''
    if not wanted:
        await reply_to_click(callback, 'Заявка уже обработана')
        return

    if approve:
        stored['prefix'] = wanted
    stored['prefix_pending'] = ''
    increment_usage('functions', 'prefix_approve' if approve else 'prefix_reject')

    await reply_to_click(callback, 'Префикс разрешён' if approve else 'Префикс отклонён', alert=False)

    if callback.message:
        mark = '✅ Разрешено' if approve else '❌ Отклонено'
        with suppress(Exception):
            await callback.message.edit_text(f'{callback.message.text or ""}\n\n{mark}', reply_markup=None)

    with suppress(Exception):
        await callback.bot.send_message(
            chat_id=int(parts[1]),
            text=(f'✨ Твой префикс «{wanted}» разрешён - он появится над новыми постами 💖'
                  if approve else
                  '💔 Такой префикс админ не разрешил. Придумай другой в меню подписки ✨'),
            reply_markup=main_keyboard(),
        )


@user.callback_query(F.data.startswith('pfxok:'))
async def cb_prefix_approve(callback: CallbackQuery):
    await moderate_prefix(callback, True)


@user.callback_query(F.data.startswith('pfxno:'))
async def cb_prefix_reject(callback: CallbackQuery):
    await moderate_prefix(callback, False)


# рекламные цитаты

@user.callback_query(F.data.startswith('ad:del:'))
async def cb_ad_delete(callback: CallbackQuery):
    if not await admin_click(callback):
        return

    parts = (callback.data or '').split(':')
    index = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else -1
    if not 0 <= index < len(data['ads']):
        await reply_to_click(callback, 'Такой цитаты уже нет - открой список заново')
        return

    data['ads'].pop(index)
    increment_usage('functions', 'ad_del')      # save_data здесь же сохраняет и список
    await reply_to_click(callback, 'Цитата удалена', alert=False)

    if callback.message:
        with suppress(Exception):
            await callback.message.edit_text(ads_text(), reply_markup=ads_keyboard(len(data['ads'])))


@user.callback_query(F.data == 'ad:add')
async def cb_ad_add(callback: CallbackQuery, state: FSMContext):
    if not await admin_click(callback):
        return

    await reply_to_click(callback)
    await state.set_state(AdminAd.waiting_text)
    if callback.message:
        with suppress(Exception):
            await callback.message.answer(
                f'Пришли текст новой рекламной цитаты (до {AD_LIMIT} символов).\n'
                'Она будет появляться под постами людей без подписки. Отменить - /cancel')


@user.callback_query(F.data == 'ad:close')
async def cb_ad_close(callback: CallbackQuery):
    await reply_to_click(callback)
    if callback.message:
        with suppress(Exception):
            await callback.message.delete()


# профиль

@user.callback_query(F.data.startswith('work:'))
async def cb_open_work(callback: CallbackQuery):
    post_id, post = own_post(callback)
    if post is None or not callback.message:
        await reply_to_click(callback, WORK_NOT_FOUND)
        return

    await reply_to_click(callback)   # снимаем «часики» до отправки фото
    with suppress(Exception):
        await callback.message.answer_photo(
            photo=post['photo'],
            caption=work_caption(post),
            reply_markup=work_keyboard(post_id),
        )


@user.callback_query(F.data.startswith('remind:'))
async def cb_remind(callback: CallbackQuery):
    post_id, post = own_post(callback)
    if post is None:
        await reply_to_click(callback, WORK_NOT_FOUND)
        return

    if post.get('awaiting'):
        await reply_to_click(callback, 'Эта работа уже ждёт ответа администратора ✨')
        return

    left = reminder_left(post)
    if left:
        await reply_to_click(callback, f'Напоминалку можно отправлять раз в сутки. Попробуй через {left} ⏳')
        return

    moderation_message_id = await send_to_moderation(callback.bot, post_id, post, '🔔 Напоминалка от автора\n\n')
    if moderation_message_id is None:
        await reply_to_click(callback, 'Не удалось отправить напоминалку. Попробуй чуть позже 💖')
        return

    post['moderation_message_id'] = moderation_message_id
    post['last_reminder_at'] = _now()
    post['awaiting'] = True
    increment_usage('functions', 'reminder')
    await reply_to_click(callback, 'Напоминалка успешно отправлена!')


@user.callback_query(F.data.startswith('act:'))
async def cb_set_actual(callback: CallbackQuery):
    post_id, post = own_post(callback)
    if post is None:
        await reply_to_click(callback, WORK_NOT_FOUND)
        return

    wanted = (callback.data or '').endswith(':1')
    if post.get('actual', True) == wanted:
        await reply_to_click(callback, ALREADY[wanted])
        return

    post['actual'] = wanted
    increment_usage('functions', 'actual' if wanted else 'not_actual')

    # статус сохранён - отвечаем до правки поста в канале, иначе запрос успевает просрочиться
    await reply_to_click(callback, STATUS_SET[wanted])

    updated = await refresh_channel_post(callback.bot, post)
    with suppress(Exception):
        await callback.message.edit_caption(caption=work_caption(post), reply_markup=work_keyboard(post_id))

    if not updated and callback.message:
        with suppress(Exception):
            await callback.message.answer(CHANNEL_UPDATE_FAILED)


@user.callback_query(F.data.startswith('status:'))
async def cb_status(callback: CallbackQuery):
    """Только для постов прошлой версии, где статус был отдельной кнопкой."""
    _, post = find_post(callback)
    await reply_to_click(callback, STATUS_INFO[bool(post.get('actual', True))] if post else 'Статус работы неизвестен')


@user.callback_query(F.data == 'profile:close')
async def cb_profile_close(callback: CallbackQuery):
    await reply_to_click(callback)
    if not callback.message:
        return

    with suppress(Exception):
        await callback.message.delete()

    with suppress(Exception):
        await callback.message.answer('🐾 Главное меню 💖', reply_markup=main_keyboard())


# Хендлеры своего префикса стоят последними специально: все кнопки меню зарегистрированы выше,
# поэтому нажатие «📝 Анкета 💖» или «👤 Профиль ✨» уводит из ввода префикса, а не становится им.

@user.message(F.text, StateFilter(SubPrefix.waiting_text))
async def cmd_prefix_text(message: Message, state: FSMContext):
    if not message.from_user:
        return

    if sub_tier(message.from_user.id) != 'pro':
        await state.clear()
        await message.answer('Свой префикс работает, пока действует продвинутая подписка ✨',
                             reply_markup=main_keyboard())
        return

    wanted = ' '.join((message.text or '').split())
    problem = prefix_problem(wanted)
    if problem:
        await message.answer(problem)
        return

    stored = data['subs'][str(message.from_user.id)]
    stored['prefix_pending'] = wanted
    increment_usage('functions', 'prefix_request')    # save_data здесь же сохраняет и заявку

    try:
        await message.bot.send_message(
            chat_id=PUBLISH_CHAT_ID,
            text=('✏️ Заявка на свой префикс\n'
                  f'Пользователь: {author_label(message.from_user.id)}\n'
                  f'ID: {message.from_user.id}\n'
                  f'Префикс: {wanted}'),
            reply_markup=prefix_keyboard(message.from_user.id),
        )
    except Exception:
        stored['prefix_pending'] = ''
        save_data(data)
        await message.answer('⚠️ Не получилось отправить префикс админу. Попробуй ещё раз через минутку 💖')
        return

    await state.clear()
    await message.answer(PREFIX_SENT, reply_markup=main_keyboard())


@user.message(StateFilter(SubPrefix.waiting_text))
async def cmd_prefix_not_text(message: Message):
    await message.answer('Нужен именно текст префикса. Или отмени через /cancel 💖')
