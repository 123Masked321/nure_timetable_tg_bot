from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging

from config.settings import TIMEZONE
from services.message_sender import send_class_notification, send_daily_schedule
from services.schedule_sync import sync_all_groups_with_retry
from database.database import AsyncSessionLocal
from database.crud import get_all_groups
from database.schedule_crud import get_class_at_time

logger = logging.getLogger(__name__)
KYIV_TZ = ZoneInfo(TIMEZONE)
scheduler = AsyncIOScheduler(timezone=KYIV_TZ)


def start_scheduler(bot):
    """Запустить планировщик задач"""

    # 1. Отправка ежедневного расписания в 7:45
    scheduler.add_job(
        send_daily_schedules_to_all,
        trigger=CronTrigger(hour=7, minute=45, timezone=KYIV_TZ),
        args=[bot],
        id="daily_schedule",
        replace_existing=True
    )

    # 2. Проверка начала пар каждую минуту
    scheduler.add_job(
        check_class_start,
        trigger=CronTrigger(minute="*", timezone=KYIV_TZ),
        args=[bot],
        id="check_classes",
        replace_existing=True
    )

    # 3. Синхронизация с CIST каждый день в 5:00
    scheduler.add_job(
        sync_all_groups_with_retry,
        trigger=CronTrigger(hour=5, minute=0, timezone=KYIV_TZ),
        id="sync_cist",
        replace_existing=True
    )

    scheduler.start()
    logger.info("Планировщик запущен")
    logger.info("Ежедневное расписание: каждый день в 7:45 (Киев)")
    logger.info("Проверка начала пар: каждую минуту (Киев)")
    logger.info("Синхронизация с CIST: каждый день в 5:00 (Киев)")


def stop_scheduler():
    """Остановить планировщик"""
    scheduler.shutdown()
    logger.info("Планировщик остановлен")


async def send_daily_schedules_to_all(bot):
    """Отправить ежедневное расписание во все группы"""
    logger.info("Отправка ежедневного расписания во все группы")

    db = AsyncSessionLocal()
    try:
        groups = await get_all_groups(db)
        print(groups)
        # Используем киевское время
        today = datetime.now(KYIV_TZ).date()

        for group in groups:
            try:
                await send_daily_schedule(bot, group, today)
            except Exception as e:
                logger.error(f"Ошибка отправки расписания в группу {group.university_group.name}: {e}")
    finally:
        await db.close()


async def check_class_start(bot):
    """Проверить, не начинается ли сейчас пара (каждую минуту)"""
    # Используем киевское время
    now = datetime.now(KYIV_TZ)
    current_time = now.time().replace(second=0, microsecond=0)
    today = now.date()

    db = AsyncSessionLocal()
    try:
        groups = await get_all_groups(db)
        for group in groups:
            schedule_class = await get_class_at_time(db, group.university_group_id, today, current_time)
            if schedule_class:
                logger.info(f"Начало пары: {schedule_class.subject_name} ({group.university_group.name})")
                try:
                    await send_class_notification(bot, group, schedule_class)
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления: {e}")
    finally:
        await db.close()
