import asyncio
from contextlib import suppress

from aiogram import Bot, Dispatcher

from handlers import user, subscription_watcher


TOKEN = "8904039692:AAFgnwCfi2enGmuh7EQnzza_Iy5kzKQA-nk"

bot = Bot(token=TOKEN)
dp = Dispatcher()
dp.include_router(user)


async def main():
    # Апдейты, накопившиеся пока бот лежал, не разбираем: нажатия кнопок из них Telegram уже
    # считает просроченными («query is too old»), а состояния анкет после рестарта всё равно пустые.
    await bot.delete_webhook(drop_pending_updates=True)

    # Фоновая задача: предупреждает об окончании подписки и снимает старые закрепы.
    watcher = asyncio.create_task(subscription_watcher(bot))
    try:
        await dp.start_polling(bot)
    finally:
        watcher.cancel()
        with suppress(asyncio.CancelledError):
            await watcher


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
