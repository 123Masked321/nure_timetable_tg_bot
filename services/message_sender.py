from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers.group import format_schedule_message
from database.crud import get_private_subscribers_by_chat
from database.database import AsyncSessionLocal
from database.schedule_crud import (
    get_schedule_for_date,
    get_links_for_subject
)
from database.models import TelegramChat, ScheduleClass
from datetime import date
import logging

logger = logging.getLogger(__name__)


async def send_class_notification(bot: Bot, chat: TelegramChat, schedule_class: ScheduleClass):
    """
    Надіслати сповіщення про початок пари.
    """
    async with AsyncSessionLocal() as db:
        try:
            logger.info(f"{int(chat.university_group_id)}, {int(schedule_class.id)}, {schedule_class.class_type}")
            links = await get_links_for_subject(
                db,
                int(chat.university_group_id),
                int(schedule_class.subject_id),
                schedule_class.class_type,
                chat.admin_user_id
            )

            message = f"🔔 <b>Пара розпочалася!</b>\n\n"
            message += f"📚 <b>{schedule_class.subject_name}</b>\n"
            message += f"⏰ {schedule_class.time_start.strftime('%H:%M')} - {schedule_class.time_end.strftime('%H:%M')}\n"

            if schedule_class.class_type:
                message += f"📖Тип заняття: {schedule_class.class_type}\n"
            if schedule_class.auditory:
                message += f"🏛 Аудиторія: {schedule_class.auditory}\n"
            if schedule_class.lector:
                message += f"👨‍🏫 Викладач: {schedule_class.lector}\n"

            message += "\n"

            if links:
                message += "<b>Посилання:</b>\n"
                for link in links:
                    message += f"🎥 <a href='{link.meeting_link}'>{link.name_link} ({link.class_type})</a>\n"
            else:
                message += "ℹ️ <i>Посилання ще не додані адміністратором</i>"

            sent_message = await bot.send_message(
                chat_id=chat.chat_id,
                text=message,
                parse_mode="HTML",
                disable_web_page_preview=True
            )

            logger.info(f"Сповіщення надіслано в групу {chat.university_group.name}")

            await send_to_private_subscriber(bot, db, chat.chat_id, chat.university_group.name, message)

        except Exception as e:
            logger.error(f"Помилка під час надсилання сповіщення: {e}")


async def send_daily_schedule(bot: Bot, chat: TelegramChat, date_obj: date):
    """
    Надіслати розклад на день о 7:45.
    """
    async with AsyncSessionLocal() as db:
        logger.info(f"Щоденне {chat.chat_id}")
        try:
            schedule = await get_schedule_for_date(db, chat.university_group_id, date_obj)

            if not schedule:
                message = (
                    f"📅 <b>Розклад на {date_obj.strftime('%d.%m.%Y')}</b>\n\n"
                    f"🎉 Сьогодні пар немає!"
                )
                await bot.send_message(chat_id=chat.chat_id, text=message, parse_mode="HTML")
                return

            formatted_schedule = format_schedule_message(
                group_name=chat.university_group.name,
                schedule=schedule,
                is_week=False
            )

            formatted_schedule += "\n💡 <i>Посилання будуть надіслані на початку кожної пари</i>"

            await bot.send_message(chat_id=chat.chat_id, text=formatted_schedule, parse_mode="HTML")
            logger.info(f"Щоденний розклад надіслано в групу {chat.university_group.name}")

            await send_to_private_subscriber(bot, db, chat.chat_id, chat.university_group.name, formatted_schedule)

        except Exception as e:
            logger.error(f"Помилка під час надсилання щоденного розкладу: {e}", exc_info=True)


async def send_to_private_subscriber(bot: Bot, db: AsyncSession, chat_id: int, group_name: str, text: str):
    """
    Надіслати повідомлення користувачам, підписаним на особисті сповіщення.
    """
    subscribers = await get_private_subscribers_by_chat(db, int(chat_id))
    text_private = f"Сповіщення з групи {group_name}:\n\n" + text
    for user_id in subscribers:
        try:
            await bot.send_message(
                chat_id=user_id.user_id,
                text=text_private,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.warning(f"Не вдалося надіслати повідомлення користувачу {user_id}: {e}")
