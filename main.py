import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats

from config.settings import BOT_TOKEN
from database.database import init_db, check_connection
from bot.handlers import admin, common, group
from bot.middlewares.anti_spam import AntiSpamMiddleware
from services.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)


private_commands = [
    BotCommand(command="my_groups", description="Переглянути групи"),
    BotCommand(command="setting_links", description="Налаштування посилань"),
    BotCommand(command="list_links", description="Переглянути всі посилання"),
    BotCommand(command="help", description="Інформація про команди"),
]

group_commands = [
    BotCommand(command="register", description="Зареєструвати групу"),
    BotCommand(command="schedule_today", description="Розклад на сьогодні"),
    BotCommand(command="schedule_week", description="Розклад на тиждень"),
    BotCommand(command="private_me", description="Надсилати в приватні"),
    BotCommand(command="stop_private", description="Не надсилати в приватні"),
    BotCommand(command="help", description="Інформація про команди"),
    BotCommand(command="change_group", description="Змінити групу"),
    BotCommand(command="sync_schedule", description="Синхронізувати розклад"),
    BotCommand(command="info", description="Інформація про групу"),
]


async def main():
    logger.info("Запуск бота...")

    if not await check_connection():
        logger.error("Не вдалося підключитися до бази даних")
        return

    try:
        await init_db()
    except Exception as e:
        logger.error(f"Помилка ініціалізації бази даних: {e}")
        return

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    dp.include_router(common.router)
    dp.include_router(group.router)
    dp.include_router(admin.router)

    dp.message.middleware(AntiSpamMiddleware(delay=3))

    start_scheduler(bot)

    await bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())
    await bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())

    try:
        logger.info("Бот запущений і готовий до роботи")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Помилка під час запуску бота: {e}")
    finally:
        stop_scheduler()
        await bot.session.close()
        logger.info("Бот зупинений")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот зупинений користувачем")