import logging
import aiohttp
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from config.settings import TIMEZONE, SCHEDULE_API_URL

logger = logging.getLogger(__name__)


class ScheduleAPI:
    def __init__(self):
        self.kyiv_tz = ZoneInfo(TIMEZONE)

    async def fetch_groups(self, session: aiohttp.ClientSession) -> Optional[Dict]:
        url = f"{SCHEDULE_API_URL}/groups"
        try:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    logger.info("Групи отримано")
                    return await response.json()
                logger.error(f"Помилка API ({response.status}) під час отримання груп")
        except Exception as e:
            logger.error(f"Помилка під час запиту до груп: {e}")
        return None

    async def parse_groups(self, session: aiohttp.ClientSession) -> List[Dict]:
        parsed = []
        groups_data = await self.fetch_groups(session)

        if not groups_data:
            logger.warning("Не вдалося отримати дані груп")
            return parsed

        if str(groups_data.get("success")).lower() != "true" or "data" not in groups_data:
            logger.warning(f"Некоректна відповідь API: {groups_data}")
            return parsed

        for item in groups_data["data"]:
            parsed.append({
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "directionId": item.get("directionId", ""),
                "specialityId": item.get("specialityId", "")
            })
        return parsed

    def find_group_by_name(self, groups_data: List[Dict], group_name: str) -> Optional[Dict]:
        normalized_name = group_name.strip().lower()
        found_group = next(
            (group for group in groups_data if group.get("name", "").strip().lower() == normalized_name),
            None
        )
        return found_group

    async def find_cist_group_id(self, group_name: str) -> Optional[str]:
        async with aiohttp.ClientSession() as session:
            parsed_groups = await self.parse_groups(session)
            if not parsed_groups:
                return None

            found_group = self.find_group_by_name(parsed_groups, group_name)

            return found_group.get("id") if found_group else None

    async def fetch_subjects(self, session: aiohttp.ClientSession, group_id: int) -> Optional[Dict]:
        url = f"{SCHEDULE_API_URL}/groups/{group_id}/subjects"
        try:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    return await response.json()
                logger.error(f"Помилка API ({response.status}) під час отримання предметів для group_id={group_id}")
        except Exception as e:
            logger.error(f"Помилка під час запиту предметів для group_id={group_id}: {e}")
        return None

    async def parse_subjects(self, session: aiohttp.ClientSession, group_id: int) -> List[Dict]:
        parsed = []
        subjects_data = await self.fetch_subjects(session, group_id)

        if not subjects_data:
            logger.warning(f"Не вдалося отримати дані предметів для group_id={group_id}")
            return parsed

        if str(subjects_data.get("success")).lower() != "true" or "data" not in subjects_data:
            logger.warning(f"Некоректна відповідь API під час отримання предметів: {subjects_data}")
            return parsed

        for item in subjects_data["data"]:
            parsed.append({
                "id": item.get("id", ""),
                "brief": item.get("brief", "").strip(),
                "name": item.get("name", "").strip()
            })
        logger.info("Предмети отримано")

        return parsed

    async def fetch_schedule_for_week(self, session: aiohttp.ClientSession, group_id: int,
                                      start_time: int, end_time: int) -> Optional[Dict]:
        url = f"{SCHEDULE_API_URL}/groups/{group_id}/schedule?startedAt={start_time}&endedAt={end_time}"
        try:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    return await response.json()
                logger.error(f"Помилка API: {response.status}")
        except Exception as e:
            logger.error(f"Помилка під час запиту розкладу: {e}")
        return None

    async def parse_schedule(self, schedule_data: Dict) -> List[Dict]:
        parsed = []
        if str(schedule_data.get("success")).lower() != "true" or "data" not in schedule_data:
            return parsed

        for item in schedule_data["data"]:
            subject = item.get("subject", {})
            teacher = item.get("teachers", [{}])[0]
            group = item.get("groups", [{}])[0]
            auditorium = item.get("auditorium", {})
            startedAt = item.get("startedAt", 0)
            endedAt = item.get("endedAt", 0)
            start_dt = datetime.fromtimestamp(startedAt, tz=self.kyiv_tz)
            end_dt = datetime.fromtimestamp(endedAt, tz=self.kyiv_tz)

            parsed.append({
                "subject": subject.get("title", ""),
                "brief": subject.get("brief", ""),
                "type": item.get("type", ""),
                "group": group.get("name", ""),
                "teacher": teacher.get("fullName", ""),
                "auditorium": auditorium.get("name", ""),
                "number_pair": item.get("numberPair", ""),
                "date": start_dt.strftime("%Y-%m-%d"),
                "day_of_week": start_dt.strftime("%A"),
                "start_time": start_dt.strftime("%H:%M"),
                "end_time": end_dt.strftime("%H:%M")
            })

        return parsed

    async def get_current_class(self, session, group_id: int) -> Optional[Dict]:
        now = datetime.now(self.kyiv_tz)

        start_of_week = datetime(now.year, now.month, now.day, tzinfo=self.kyiv_tz) - timedelta(days=now.weekday())
        end_of_week = start_of_week + timedelta(days=7, hours=-1, minutes=-1)

        start_ts = int(start_of_week.timestamp())
        end_ts = int(end_of_week.timestamp())

        schedule_data = await self.fetch_schedule_for_week(session, group_id, start_ts, end_ts)
        if not schedule_data:
            return None

        classes = await self.parse_schedule(schedule_data)
        if not classes:
            return None

        for cls in classes:
            try:
                start = datetime.strptime(cls["start_time"], "%Y-%m-%d %H:%M").replace(tzinfo=self.kyiv_tz)
                end = datetime.strptime(cls["end_time"], "%Y-%m-%d %H:%M").replace(tzinfo=self.kyiv_tz)

                if start <= now <= end:
                    return cls
            except Exception as e:
                logger.error(f"Помилка під час обробки часу пари: {e}")

        return None
