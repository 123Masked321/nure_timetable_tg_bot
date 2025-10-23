from datetime import datetime, timedelta, date
import aiohttp
from sqlalchemy import select

from database.crud import get_university_group_by_id
from database.database import AsyncSessionLocal
from database.schedule_crud import (
    create_schedule_class,
    clear_group_schedule,
    delete_old_schedule,
    create_subject_for_group, get_subject_by_name, get_subjects_for_group, delete_subject_by_id
)
from services.schedule_api import ScheduleAPI
from database.models import UniversityGroup
import logging
from zoneinfo import ZoneInfo
from config.settings import TIMEZONE
import asyncio

logger = logging.getLogger(__name__)

KYIV_TZ = ZoneInfo(TIMEZONE)

MAX_RETRY_ATTEMPTS = 5

api_client = ScheduleAPI()


async def sync_group_schedule_to_db(university_group: UniversityGroup) -> bool:
    """Синхронізувати розклад для однієї університетської групи"""
    logger.info(f"Початок синхронізації групи {university_group.name}")

    async with AsyncSessionLocal() as db:
        try:

            async with aiohttp.ClientSession() as session:
                subjects_from_api = await api_client.parse_subjects(session, int(university_group.cist_group_id))

            if not subjects_from_api:
                logger.error(f"Не вдалося отримати предмети з CIST для {university_group.name}")
                return False

            subjects_from_db = await get_subjects_for_group(db, university_group.id)

            subjects_names_from_db = {subject.name for subject in subjects_from_db}
            subjects_names_from_api = {subject_api["name"] for subject_api in subjects_from_api}

            new_subjects = []
            old_subjects = []
            for subject in subjects_from_api:
                if subject["name"] not in subjects_names_from_db:
                    new_subjects.append(subject)

            for subject in subjects_from_db:
                if subject.name not in subjects_names_from_api:
                    old_subjects.append(subject)

            for old_subject in old_subjects:
                await delete_subject_by_id(db, int(old_subject.id))

            for new_subject in new_subjects:
                await create_subject_for_group(db, university_group.id, new_subject["name"], new_subject["brief"])

            logger.info(f"Видалено старих предметів: {len(old_subjects)}")
            logger.info(f"Додано нових предметів: {len(new_subjects)}")

            today = datetime.now(KYIV_TZ)
            start_ts = int(today.timestamp())
            end_ts = int((today + timedelta(days=7)).timestamp())

            async with aiohttp.ClientSession() as session:
                events_raw = await api_client.fetch_schedule_for_week(
                    session,
                    university_group.cist_group_id,
                    start_ts,
                    end_ts
                )

            if not events_raw:
                logger.error(f"Не вдалося отримати розклад з CIST для {university_group.name}")
                return False

            events = api_client.parse_schedule(events_raw)

            await clear_group_schedule(db, university_group.id)
            changes_count = 0

            for event in events:
                event_date = datetime.strptime(event["date"], "%Y-%m-%d").date()
                event_time_start = datetime.strptime(event["start_time"], "%H:%M").time()
                event_time_end = datetime.strptime(event["end_time"], "%H:%M").time()
                subject = await get_subject_by_name(db, university_group.id, event["subject"])

                await create_schedule_class(
                    db=db,
                    university_group_id=university_group.id,
                    subject_id=subject.id,
                    date_obj=event_date,
                    day_of_week=event["day_of_week"],
                    time_start=event_time_start,
                    time_end=event_time_end,
                    subject_name=event["subject"],
                    subject_brief=event["brief"],
                    class_type=event.get("type"),
                    auditory=event.get("auditorium"),
                    lector=event.get("teacher"),
                )
                changes_count += 1


            await delete_old_schedule(db, university_group.id, date.today())
            logger.info(f"Синхронізація завершена. Додано {changes_count} пар.")
            return True

        except Exception as e:
            logger.error(f"Помилка синхронізації для {university_group.name}: {e}")
            return False


async def sync_all_groups_with_retry():
    """Синхронізувати всі університетські групи з повторними спробами"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(UniversityGroup))
        groups = result.scalars().all()

        if not groups:
            logger.info("Немає зареєстрованих груп для синхронізації")
            return

        logger.info(f"Початок синхронізації {len(groups)} груп")

        for group in groups:
            for attempt in range(MAX_RETRY_ATTEMPTS):
                success = await sync_group_schedule_to_db(group)
                if success:
                    break

                logger.warning(
                    f"Помилка синхронізації для {group.name}, спроба {attempt + 1}/{MAX_RETRY_ATTEMPTS}"
                )
                await asyncio.sleep(60)  # пауза перед повтором


async def initial_sync_on_register(university_group_id: int) -> bool:
    """Початкова синхронізація при реєстрації групи"""
    async with AsyncSessionLocal() as db:
        university_group = await get_university_group_by_id(db, university_group_id)
        if not university_group:
            logger.error(f"Група з ID {university_group_id} не знайдена")
            return False

        return await sync_group_schedule_to_db(university_group)


async def load_subjects_for_group(university_group_id: int, cist_group_id: int) -> bool:
    """
    Завантажує всі предмети групи з CIST API і записує їх у базу даних.

    Args:
        university_group_id: ID університетської групи в нашій БД (не використовується)
        cist_group_id: ID групи в системі CIST
    """
    async with AsyncSessionLocal() as db:
        async with aiohttp.ClientSession() as session:
            try:
                subjects = await api_client.parse_subjects(session, cist_group_id)
                if not subjects:
                    logger.warning(f"Порожній список предметів для групи {cist_group_id}")
                    return False

                added_count = 0
                for subj in subjects:
                    name = subj.get("name", "").strip()
                    brief = subj.get("brief", "").strip()

                    if not name or not brief:
                        logger.warning("Пропущено предмет без назви або brief")
                        continue

                    subject = await create_subject_for_group(
                        db,
                        group_id=university_group_id,
                        name=name,
                        brief=brief
                    )
                    if subject:
                        added_count += 1
                await db.commit()

                logger.info(f"Завантажено/оновлено {added_count} предметів для групи {cist_group_id}")
                return True


            except Exception as e:
                logger.error(f"Помилка при завантаженні предметів: {e}")
                return False
