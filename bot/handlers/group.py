from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, ChatMemberUpdated
from sqlalchemy.exc import SQLAlchemyError
from database.database import AsyncSessionLocal
from database.crud import (
    create_university_group, create_telegram_chat, get_telegram_chat_by_chat_id, get_university_group_by_id,
    cleanup_unused_university_groups, switch_telegram_chat_group, get_university_group_by_cist_id,
    add_private_subscriber, remove_private_subscriber, delete_telegram_chat
)
from services.schedule_api import ScheduleAPI
from services.schedule_sync import initial_sync_on_register, load_subjects_for_group
from bot.filters.admin_filter import IsGroupAdmin
from database.schedule_crud import (
    get_schedule_for_date,
    get_schedule_for_week,
    get_links_by_group,
    get_subjects_for_group
)
from datetime import date, timedelta
import re
import logging

logger = logging.getLogger(__name__)
api_client = ScheduleAPI()
router = Router()


def format_schedule_message(group_name: str, schedule: list, is_week: bool):
    if not schedule:
        return f"📭 Розклад поки порожній. Він буде оновлено при наступній синхронізації."

    day_names = {
        "Monday": "Понеділок", "Tuesday": "Вівторок", "Wednesday": "Середа",
        "Thursday": "Четвер", "Friday": "Пʼятниця", "Saturday": "Субота", "Sunday": "Неділя"
    }

    text = f"📅 <b>Розклад для {group_name}</b>\n\n"
    days = {}
    for cls in schedule:
        days.setdefault(cls.date, []).append(cls)

    for day, classes in sorted(days.items()):
        day_name = day_names.get(classes[0].day_of_week, classes[0].day_of_week)
        text += f"<b>{day_name}, {day.strftime('%d.%m')}</b>\n"
        for c in sorted(classes, key=lambda x: x.time_start):
            text += f"  • {c.time_start.strftime('%H:%M')} (Київ) - {c.subject_name}"
            if c.class_type:
                text += f" ({c.class_type})"
            text += "\n"
        text += "\n"
    return text


@router.message(Command("register"))
async def cmd_register(message: Message):
    if message.chat.type == "private":
        await message.answer("❌ Ця команда працює лише в групових чатах")
        return

    command_args = message.text.split(maxsplit=1)
    if len(command_args) < 2:
        await message.answer(
            "❌ Не вказано назву групи.\n"
            "Приклад: /register ПЗПІ-24-1"
        )
        return

    chat_id = int(message.chat.id)
    user_id = message.from_user.id
    username = message.from_user.username
    chat_title = message.chat.title or "Невідома група"

    async with AsyncSessionLocal() as db:
        try:
            existing_chat = await get_telegram_chat_by_chat_id(db, chat_id)
            if existing_chat:
                uni_group = await get_university_group_by_id(db, existing_chat.university_group_id)
                await message.answer(
                    f"ℹ️ Група вже зареєстрована!\n\n"
                    f"👨‍💼 Адміністратор: @{existing_chat.admin_username or 'адмін'}\n"
                    f"📚 Назва групи: {uni_group.name}\n"
                    f"🆔 CIST ID: {uni_group.cist_group_id}"
                )
                return

            waiting_msg = await message.answer("🔍 Шукаю групу в системі ХНУРЕ...")

            command_args = message.text.split(maxsplit=1)
            group_name = None
            if len(command_args) > 1:
                group_name = command_args[1].strip()
            else:
                match = re.search(r'[А-ЯІЇЄа-яіїє]+-\d{2}-\d', chat_title)
                if match:
                    group_name = match.group(0)
                else:
                    group_name = chat_title

            cist_group_id = await api_client.find_cist_group_id(group_name)
            if not cist_group_id:
                await waiting_msg.edit_text(
                    f"❌ Групу '{group_name}' не знайдено в системі CIST.\n\n"
                    f"💡 Переконайтеся, що назва групи написана правильно.\n"
                    f"Приклад: ПЗПІ-24-1, КБІКС-23-2\n\n"
                    f"Або змініть назву чату на код групи та спробуйте ще раз."
                )
                return

            university_group = await create_university_group(
                db=db,
                cist_group_id=int(cist_group_id),
                name=group_name
            )

            telegram_chat = await create_telegram_chat(
                db=db,
                chat_id=chat_id,
                university_group_id=university_group.id,
                admin_user_id=user_id,
                admin_username=username
            )

            await waiting_msg.edit_text(
                f"✅ Групу знайдено!\n"
                f"📚 {group_name} (ID: {cist_group_id})\n\n"
                f"🔄 Завантажую предмети..."
            )

            subjects_loaded = await load_subjects_for_group(university_group.id, int(cist_group_id))
            if not subjects_loaded:
                logger.warning(f"Не вдалося завантажити предмети для групи {group_name}")

            await waiting_msg.edit_text("🔄 Завантажую розклад...")

            sync_success = await initial_sync_on_register(university_group.id)

            if sync_success:
                await waiting_msg.edit_text(
                    f"✅ Група успішно зареєстрована!\n\n"
                    f"👨‍💼 Адміністратор: @{username or 'ви'}\n"
                    f"📚 Назва групи: {group_name}\n"
                    f"🆔 CIST ID: {cist_group_id}\n\n"
                    f"📅 Розклад завантажено на наступні 7 днів\n\n"
                    f"ℹ️ Тепер адміністратор може:\n"
                    f"• Додавати посилання на пари через /add_links в особистих повідомленнях з ботом\n"
                    f"• Переглядати розклад командами /schedule_today та /schedule_week\n\n"
                    f"🔔 Бот автоматично:\n"
                    f"• Відправить розклад щодня о 7:45\n"
                    f"• Надішле нагадування на початку кожної пари\n"
                    f"• Оновить розклад щодня о 5:00\n\n"
                    f"⚠️ Тільки адміністратор може використовувати команди управління ботом у цій групі!"
                )
            else:
                await waiting_msg.edit_text(
                    f"⚠️ Група зареєстрована, але не вдалося завантажити розклад.\n\n"
                    f"📚 {group_name}\n"
                    f"👨‍💼 Адміністратор: @{username or 'ви'}\n\n"
                    f"Розклад буде завантажено автоматично о 5:00 ранку.\n"
                    f"Або спробуйте команду /sync_schedule пізніше."
                )
        except Exception as e:
            logger.error(f"Помилка реєстрації: {e}")
            await message.answer(f"❌ Помилка реєстрації: {e}")


@router.message(Command("change_group"), IsGroupAdmin())
async def cmd_change_group(message: Message):
    if message.chat.type == "private":
        await message.answer("❌ Ця команда працює лише в групових чатах")
        return

    command_args = message.text.split(maxsplit=1)
    if len(command_args) < 2:
        await message.answer(
            "❌ Не вказано назву групи.\n"
            "Приклад: /change_group ПЗПІ-24-1"
        )
        return

    new_group_name = command_args[1].strip()
    chat_id = int(message.chat.id)

    async with AsyncSessionLocal() as db:
        try:
            telegram_chat = await get_telegram_chat_by_chat_id(db, chat_id)
            if not telegram_chat:
                await message.answer("❌ Група не зареєстрована. Використайте /register")
                return

            old_university_group_id = telegram_chat.university_group_id

            waiting_msg = await message.answer(f"🔍 Шукаю групу '{new_group_name}' в системі ХНУРЕ...")

            cist_group_id = await api_client.find_cist_group_id(new_group_name)
            if not cist_group_id:
                await waiting_msg.edit_text(
                    f"❌ Групу '{new_group_name}' не знайдено в системі CIST.\n\n"
                    f"💡 Переконайтеся, що назва групи написана правильно."
                )
                return

            new_university_group = await get_university_group_by_cist_id(db, int(cist_group_id))

            if not new_university_group:
                new_university_group = await create_university_group(
                    db=db,
                    cist_group_id=int(cist_group_id),
                    name=new_group_name
                )
                await waiting_msg.delete()

                await load_subjects_for_group(new_university_group.id, int(cist_group_id))

                sync_success = await initial_sync_on_register(new_university_group.id)
            else:
                await waiting_msg.delete()
                sync_success = True

            await switch_telegram_chat_group(db, chat_id, new_university_group.id)

            await cleanup_unused_university_groups(db)

            if sync_success:
                await message.answer(
                    f"✅ Чат успішно переключено на групу <b>{new_group_name}</b>!\n"
                    f"Розклад оновлено."
                )
            else:
                await message.answer(
                    f"⚠️ Чат переключено на групу <b>{new_group_name}</b>, але не вдалося синхронізувати розклад.\n"
                    "Спробуйте пізніше."
                )

        except Exception as e:
            logger.error(f"Помилка при зміні групи: {e}", exc_info=True)
            await message.answer("❌ Виникла помилка при зміні групи. Спробуйте пізніше.")


@router.message(Command("schedule_today"))
async def cmd_schedule_today(message: Message):
    if message.chat.type == "private":
        await message.answer("❌ Ця команда працює лише в групових чатах")
        return

    async with AsyncSessionLocal() as db:
        telegram_chat = await get_telegram_chat_by_chat_id(db, int(message.chat.id))
        if not telegram_chat:
            await message.answer("❌ Група не зареєстрована. Використайте /register")
            return

        university_group = await get_university_group_by_id(db, telegram_chat.university_group_id)
        today = date.today()
        schedule = await get_schedule_for_date(db, university_group.id, today)

        formatted_message = format_schedule_message(university_group.name, schedule, is_week=False)
        await message.answer(formatted_message, parse_mode="HTML")


@router.message(Command("schedule_week"))
async def cmd_schedule_week(message: Message):
    if message.chat.type == "private":
        await message.answer("❌ Ця команда працює лише в групових чатах")
        return

    async with AsyncSessionLocal() as db:
        telegram_chat = await get_telegram_chat_by_chat_id(db, int(message.chat.id))
        if not telegram_chat:
            await message.answer("❌ Група не зареєстрована. Використайте /register")
            return

        university_group = await get_university_group_by_id(db, telegram_chat.university_group_id)
        today = date.today()
        week_end = today + timedelta(days=7)
        schedule = await get_schedule_for_week(db, university_group.id, today, week_end)

        formatted_message = format_schedule_message(university_group.name, schedule, is_week=True)
        await message.answer(formatted_message, parse_mode="HTML")


@router.message(Command("info"))
async def cmd_info(message: Message):
    if message.chat.type == "private":
        await message.answer("❌ Ця команда працює лише в групових чатах")
        return

    chat_id = int(message.chat.id)
    async with AsyncSessionLocal() as db:
        telegram_chat = await get_telegram_chat_by_chat_id(db, chat_id)
        if not telegram_chat:
            await message.answer("❌ Група не зареєстрована. Використайте /register")
            return

        university_group = await get_university_group_by_id(db, telegram_chat.university_group_id)

        subjects_count = len(await get_subjects_for_group(db, university_group.id))
        links_count = len(await get_links_by_group(db, university_group.id))

        created_at = telegram_chat.created_at.strftime('%d.%m.%Y')

        await message.answer(
            f"ℹ️ <b>Інформація про групу</b>\n\n"
            f"📚 Назва: {university_group.name}\n"
            f"🆔 CIST ID: {university_group.cist_group_id}\n"
            f"👨‍💼 Адміністратор: @{telegram_chat.admin_username or 'адмін'}\n"
            f"📖 Предметів у розкладі: {subjects_count}\n"
            f"🔗 Додано посилань: {links_count}\n"
            f"📅 Зареєстрована: {created_at}\n\n"
            f"⚠️ Тільки адміністратор може керувати ботом у цій групі",
            parse_mode="HTML"
        )


@router.message(Command("sync_schedule"), IsGroupAdmin())
async def cmd_sync_schedule(message: Message):
    if message.chat.type == "private":
        await message.answer("❌ Ця команда працює лише в групових чатах")
        return

    chat_id = int(message.chat.id)
    async with AsyncSessionLocal() as db:
        telegram_chat = await get_telegram_chat_by_chat_id(db, chat_id)
        if not telegram_chat:
            await message.answer("❌ Група не зареєстрована. Використайте /register")
            return

        university_group = await get_university_group_by_id(db, telegram_chat.university_group_id)

        waiting_msg = await message.answer("🔄 Синхронізація розкладу...")
        sync_success = await initial_sync_on_register(university_group.id)

        if sync_success:
            await waiting_msg.edit_text("✅ Розклад успішно оновлено!")
        else:
            await waiting_msg.edit_text(
                "❌ Не вдалося оновити розклад.\n"
                "CIST API може бути тимчасово недоступний.\n"
                "Спробуйте пізніше."
            )


@router.message(Command("private_me"))
async def cmd_private_me(message: Message):
    if message.chat.type == "private":
        await message.answer("❌ Ця команда працює лише в групових чатах")
        return

    user = message.from_user
    chat_id = message.chat.id

    async with AsyncSessionLocal() as db:
        telegram_chat = await get_telegram_chat_by_chat_id(db, chat_id)
        if not telegram_chat:
            await message.answer("❌ Група не зареєстрована. Використайте /register")
            return

        subscriber = await add_private_subscriber(
            db=db,
            user_id=user.id,
            chat_id=chat_id,
            username=user.username
        )

        if not subscriber:
            await message.reply(f"Ти (@{user.username}) вже зареєстрований")
            return

        try:
            await message.bot.send_message(
                user.id,
                f"🔔 Привіт, {user.first_name or user.username}!\n"
                f"Тепер ти отримуєш сповіщення з групи: {message.chat.title}"
            )
            await message.answer(f"✅ Теперь ты (@{user.username}) будешь получать личные уведомления!")
        except Exception:
            await message.reply(
                "⚠️ Я не можу написати тобі в особисті повідомлення.\n"
                "Будь ласка, спочатку відкрий діалог зі мною та натисни ➜ /start"
            )


@router.message(Command("stop_private"))
async def cmd_stop_private(message: Message):
    if message.chat.type == "private":
        await message.answer("❌ Ця команда працює лише в групових чатах")
        return

    async with AsyncSessionLocal() as db:
        telegram_chat = await get_telegram_chat_by_chat_id(db, message.chat_id)
        if not telegram_chat:
            await message.answer("❌ Група не зареєстрована. Використайте /register")
            return

        removed = await remove_private_subscriber(
            db=db,
            user_id=message.from_user.id,
            chat_id=message.chat.id
        )
        if removed:
            await message.answer("🛑 Ти більше не отримуєш особисті сповіщення.")
        else:
            await message.answer("ℹ️ Ти не був підписаний на сповіщення.")


@router.message(Command("delete_chat"), IsGroupAdmin())
async def cmd_delete_chat(message: Message):
    if message.chat.type == "private":
        await message.answer("❌ Ця команда працює лише в групових чатах")
        return

    async with AsyncSessionLocal() as db:
        telegram_chat = await get_telegram_chat_by_chat_id(db, message.chat.id)
        if not telegram_chat:
            await message.answer("❌ Група не зареєстрована. Використайте /register")
            return

        try:
            await delete_telegram_chat(db, telegram_chat)
        except SQLAlchemyError as e:
            await message.answer("❌ Помилка: група не була видалена.")
            logger.exception(f"Помилка при видаленні чата {message.chat.id}: {e}")
        else:
            await message.answer(
                "✅ Група була видалена. Її може зареєструвати інший адмін або бот може бути видалений з групи."
            )





@router.my_chat_member()
async def on_bot_added(event: ChatMemberUpdated):
    if event.new_chat_member.status in ["member", "administrator"]:
        await event.answer(
            "👋 Привіт! Я бот для керування розкладом для ХНУРЕ.\n\n"
            "📝 Щоб почати роботу:\n"
            "1️⃣ Використайте команду /register з назвою групи\n"
            "2️⃣ Той, хто виконає цю команду першим, стане адміністратором групи\n"
            "3️⃣ Тільки адміністратор зможе керувати ботом\n\n"
            "💡 Після реєстрації адміністратор зможе додавати посилання на відвідування, конференції і т. д. через особисті повідомлення з ботом."
        )