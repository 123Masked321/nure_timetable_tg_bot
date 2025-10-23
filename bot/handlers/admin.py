from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging


from database.database import AsyncSessionLocal
from database.crud import (
    get_all_university_groups_by_admin, get_university_group_by_id
)
from database.schedule_crud import (
    get_subjects_for_group, update_link,create_link_for_subject, get_links_for_subject, get_subject_by_id,
    get_links_by_owner, delete_link, get_link_by_id
)
from bot.keyboards.admin_kb import build_groups_keyboard, build_subjects_keyboard, build_links_list_keyboard, \
    build_type_class_keyboard, build_action_keyboard, build_skip_keyboard

router = Router()

logger = logging.getLogger(__name__)


class ChangeLinkStates(StatesGroup):
    waiting_for_action = State()
    waiting_for_group_selection = State()
    waiting_for_subject_selection = State()
    waiting_for_link_type = State()
    waiting_for_name_link = State()
    waiting_for_link = State()
    waiting_for_select_link = State()
    waiting_for_new_name_link = State()
    waiting_for_new_link = State()


class ShowLinkStates(StatesGroup):
    waiting_for_group_selection = State()


@router.message(Command("my_groups"))
async def cmd_my_groups(message: Message):
    if message.chat.type != "private":
        await message.answer(
            "⚠️ <b>Ця команда працює лише у приватних повідомленнях із ботом.</b>\n\n"
            f"📩 Напишіть мені в особисті: @{(await message.bot.me()).username}",
            parse_mode="HTML"
        )
        return

    db = AsyncSessionLocal()
    try:
        groups = await get_all_university_groups_by_admin(db, message.from_user.id)

        if not groups:
            await message.answer(
                "❌ У вас немає груп для керування.\n\n"
                "Щоб керувати групою:\n"
                "1. Додайте мене до групового чату\n"
                "2. Використайте команду /register у групі"
            )
            return

        text = "<b>📋 Ваші групи:</b>\n\n"
        for i, group in enumerate(groups, start=1):
            text += f"{i}. <b>{group.name}</b> — ID: <code>{group.cist_group_id}</code>\n"

        await message.answer(text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Сталася помилка my_groups:{e}")
    finally:
        await db.close()


@router.message(Command("setting_links"))
async def setting_links(message: Message, state: FSMContext):
    if message.chat.type != "private":
        await message.answer(
            "⚠️ <b>Ця команда працює лише у приватних повідомленнях із ботом.</b>\n\n"
            f"📩 Напишіть мені в особисті: @{(await message.bot.me()).username}",
            parse_mode="HTML"
        )
        return
    db = AsyncSessionLocal()
    try:
        groups = await get_all_university_groups_by_admin(db, message.from_user.id)

        if not groups:
            await message.answer(
                "❌ У вас немає груп для керування.\n\n"
                "Щоб керувати групою:\n"
                "1. Додайте мене до групового чату\n"
                "2. Використайте команду /register у групі"
            )
            return
        await state.clear()
        keyboard = build_action_keyboard()
        await message.answer("Оберіть дію:", reply_markup=keyboard)
        await state.set_state(ChangeLinkStates.waiting_for_action)
    except Exception as e:
        logger.error(f"Сталася помилка:{e}")
    finally:
        await db.close()


@router.callback_query(F.data.startswith("select_action_"), ChangeLinkStates.waiting_for_action)
async def cmd_add_link(callback_query: CallbackQuery, state: FSMContext):
    action = callback_query.data.split("_")[2]
    await state.update_data(action=action)
    db = AsyncSessionLocal()
    try:
        groups = await get_all_university_groups_by_admin(db, callback_query.from_user.id)
        if len(groups) == 1:
            group_id = groups[0].id
            await state.update_data(group_id=group_id)
            sent_msg = await callback_query.message.edit_text(
                f"📝 Добавление ссылки для группы: <b>{groups[0].name}</b>\n\n"
                "📚 Загружаю список предметов...",
                parse_mode="HTML"
            )
            await show_subjects_keyboard(sent_msg, state, group_id)
            return

        keyboard = build_groups_keyboard(groups)
        await callback_query.message.edit_text("📚 Выберите группу, для которой хотите добавить ссылку:",
                                               reply_markup=keyboard)
        await state.set_state(ChangeLinkStates.waiting_for_group_selection)
    except Exception as e:
        logger.error(f"Сталася помилка:{e}")
    finally:
        await db.close()


@router.callback_query(F.data.startswith("select_group_"), ChangeLinkStates.waiting_for_group_selection)
async def process_group_selection(callback_query: CallbackQuery, state: FSMContext):
    group_id = int(callback_query.data.split("_")[2])
    await state.update_data(group_id=group_id)
    await callback_query.message.edit_text("📚 Завантажую список предметів...")
    await show_subjects_keyboard(callback_query.message, state, group_id)


async def show_subjects_keyboard(message: Message, state: FSMContext, group_id: int):
    db = AsyncSessionLocal()
    try:
        subjects = await get_subjects_for_group(db, group_id)
        if not subjects:
            await message.answer("❌ У розкладі групи поки немає предметів. Дочекайтеся синхронізації.")
            await state.clear()
            return

        keyboard = build_subjects_keyboard(subjects)
        await message.edit_text("📖 Оберіть предмет:", reply_markup=keyboard)
        await state.set_state(ChangeLinkStates.waiting_for_subject_selection)
    finally:
        await db.close()


@router.callback_query(F.data.startswith("select_subject_"), ChangeLinkStates.waiting_for_subject_selection)
async def process_subject_selection(callback_query: CallbackQuery, state: FSMContext):
    db = AsyncSessionLocal()
    try:
        subject_id = callback_query.data.split("_", 2)[2]
        await state.update_data(subject_id=subject_id)
        subject_name = (await get_subject_by_id(db, int(subject_id))).name
    finally:
        await db.close()

    await callback_query.message.edit_text(
        f"🔗 Додавання посилання для предмета: <b>{subject_name}</b>\n\n"
        "⌨️ Оберіть тип заняття:",
        reply_markup=build_type_class_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(ChangeLinkStates.waiting_for_link_type)



@router.callback_query(F.data.startswith("select_type_"), ChangeLinkStates.waiting_for_link_type)
async def process_link_type(callback_query: CallbackQuery, state: FSMContext):
    data = callback_query.data.split("_", 2)[2]
    state_data = await state.get_data()
    selected = state_data.get("selected_types", [])

    if data == "done":
        if not selected:
            await callback_query.message.delete()
            await callback_query.message.answer(text="⚠️ Ви не вибрали жодного типу занять!",
                                                   reply_markup=build_type_class_keyboard(selected_types=selected))
            return
        await state.update_data(link_types=selected)
        if state_data["action"] == "add":
            await callback_query.message.edit_text(
                f"📌 Выбрано типів занять: {', '.join(selected) if selected else 'не выбрано'}\n"
                "📌 Введіть назву для посилання:"
            )
            await state.set_state(ChangeLinkStates.waiting_for_name_link)
            return
        db = AsyncSessionLocal()
        try:
            group_id = state_data["group_id"]
            subject_id = state_data["subject_id"]

            all_links = []
            for class_type in selected:
                links = await get_links_for_subject(
                    db, int(group_id), int(subject_id), class_type, callback_query.from_user.id
                )
                all_links.extend(links)

            if not all_links:
                await callback_query.message.edit_text("❌ Посилання не знайдені для вибраних типів.")
                await state.clear()
                return

            text = "Оберіть посилання для вибраних типів занять:"
            keyboard = build_links_list_keyboard(all_links)
            await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await state.set_state(ChangeLinkStates.waiting_for_select_link)

        finally:
            await db.close()
        return

    if data in selected:
        selected.remove(data)
    else:
        selected.append(data)

    await state.update_data(selected_types=selected)

    # Обновляем клавиатуру с галочками
    await callback_query.message.edit_reply_markup(
        reply_markup=build_type_class_keyboard(selected_types=selected)
    )


@router.message(ChangeLinkStates.waiting_for_name_link)
async def process_meeting_link(message: Message, state: FSMContext):
    name_link = message.text.strip() if message.text.strip() != "-" else None
    await state.update_data(name_link=name_link)
    await message.bot.delete_message(chat_id=message.chat.id, message_id=message.message_id - 1)
    await message.delete()
    await message.answer("✅ Введіть посилання:")
    await state.set_state(ChangeLinkStates.waiting_for_link)


@router.message(ChangeLinkStates.waiting_for_link)
async def process_attendance_link(message: Message, state: FSMContext):
    link = message.text.strip() if message.text.strip() != "-" else None
    data = await state.get_data()
    db = AsyncSessionLocal()
    try:
        group_id = int(data["group_id"])
        subject_id = int(data["subject_id"])
        link_types = data["link_types"]
        name_link = data["name_link"]
        for link_type in link_types:
            await create_link_for_subject(
                db=db,
                university_group_id=group_id,
                subject_id=subject_id,
                owner_user_id=int(message.from_user.id),
                class_type=link_type,
                name_link=name_link,
                meeting_link=link
            )
        subject_name = (await get_subject_by_id(db, subject_id)).name
        await message.delete()
        await message.bot.delete_message(message.chat.id, message.message_id-1)
        await message.answer(
            text=f"✅ Посилання для <b>{subject_name} ({link_types})</b> додані!",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"❌ Помилка при зберіганні. Спробуйте знову або напишіть @shallbewolk")
        logger.error(f"Сталася помилка при зберіганні:{e}")
    finally:
        await db.close()
        await state.clear()


@router.callback_query(F.data.startswith("select_link_"), ChangeLinkStates.waiting_for_select_link)
async def process_deleting_link(callback_query: CallbackQuery, state: FSMContext):
    data = callback_query.data.split("_", 2)[2]
    state_data = await state.get_data()
    selected = state_data.get("selected_links", [])
    db = AsyncSessionLocal()
    try:
        group_id = state_data.get("group_id")
        subject_id = state_data.get("subject_id")
        selected_types = state_data.get("selected_types")

        all_links = []
        for class_type in selected_types:
            links = await get_links_for_subject(
                db, int(group_id), int(subject_id), class_type, callback_query.from_user.id
            )
            all_links.extend(links)
        if data == "done":
            if not selected:
                await callback_query.message.edit_text(text="⚠️ Ви не вибрали жодного посилання!",
                                                       reply_markup=build_links_list_keyboard(links=all_links,
                                                                                              selected_links=selected))
                return

            if state_data["action"] == "delete":
                subject_name = (await get_subject_by_id(db, int(state_data["subject_id"]))).name
                text = f"Посилання для предмету {subject_name}\n"
                for link_id in selected:
                    link = await get_link_by_id(db, int(link_id))
                    result = await delete_link(db, int(link_id))
                    text += f"{link.name_link}({link.class_type})"
                    text += "✅ видалено\n" if result else "❌ не видалено\n"
                await callback_query.message.edit_text(text=text)
                await state.clear()
                return
            await callback_query.message.delete()
            await callback_query.message.answer(
                text="Введіть нову назву (опціонально):",
                reply_markup=build_skip_keyboard())
            await state.set_state(ChangeLinkStates.waiting_for_new_name_link)
            return
        if int(data) in selected:
            selected.remove(int(data))
        else:
            selected.append(int(data))

        await state.update_data(selected_links=selected)

        await callback_query.message.edit_reply_markup(
            reply_markup=build_links_list_keyboard(links=all_links, selected_links=selected)
        )
    except Exception as e:
        await callback_query.message.edit_text(f"❌ Помилка при видаленні. Спробуйте знову або напишіть @shallbewolk")
        logger.error(f"Сталася помилка при видаленні:{e}")
    finally:
        await db.close()


@router.message(ChangeLinkStates.waiting_for_new_name_link)
async def process_new_name_link(message: Message, state: FSMContext):

    if message.text == "Пропустити":
        new_name = None
    else:
        new_name = message.text.strip()

    await message.delete()
    await message.bot.delete_message(chat_id=message.chat.id, message_id=message.message_id - 1)
    await state.update_data(new_name_link=new_name)
    await message.answer(
        text="Введіть нове посилання(опціонально):",
        reply_markup=build_skip_keyboard()
    )
    await state.set_state(ChangeLinkStates.waiting_for_new_link)


@router.message(ChangeLinkStates.waiting_for_new_link)
async def process_new_link(message: Message, state: FSMContext):
    if message.text == "Пропустити":
        new_link = None
    else:
        new_link = message.text.strip()
    data = await state.get_data()
    await message.delete()
    await message.bot.delete_message(chat_id=message.chat.id, message_id=message.message_id - 1)
    db = AsyncSessionLocal()
    try:
        selected_links = data.get("selected_links")
        subject_name = (await get_subject_by_id(db, int(data["subject_id"]))).name
        text = f"Посилання для предмету {subject_name}\n"
        for link_id in selected_links:
            new_class_link = await update_link(db, int(link_id), data["new_name_link"], new_link)
            text += f"{new_class_link.name_link}({new_class_link.class_type}) було оновлено\n"
        await message.answer(text=text)
        await state.clear()
        return
    except Exception as e:
        await message.answer(f"❌ Помилка при оновленні. Спробуйте знову або напишіть @shallbeewolk")
        logger.error(f"Сталася помилка при оновленні:{e}")
    finally:
        await db.close()


@router.message(Command("list_links"))
async def cmd_list_links(message: Message, state: FSMContext):
    if message.chat.type != "private":
        await message.answer(
            "⚠️ <b>Ця команда працює лише у приватних повідомленнях із ботом.</b>\n\n"
            f"📩 Напишіть мені в особисті: @{(await message.bot.me()).username}",
            parse_mode="HTML"
        )
        return

    async with AsyncSessionLocal() as db:
        try:
            groups = await get_all_university_groups_by_admin(db, message.from_user.id)
            if not groups:
                await message.answer(
                    "❌ У вас немає груп для керування.\n\n"
                    "Щоб керувати групою:\n"
                    "1. Додайте мене до групового чату\n"
                    "2. Використайте команду /register у групі"
                )
                return

            if len(groups) == 1:
                await show_links_list(message, groups[0].id, groups[0].name, message.from_user.id)
                return

            keyboard = build_groups_keyboard(groups)
            await message.answer("📚 Выберите группу, чтобы посмотреть ссылки:", reply_markup=keyboard)
            await state.set_state(ShowLinkStates.waiting_for_group_selection)
        except Exception as e:
            logger.error(f"Сталася помилка під час отримання списку посилань:{e}")


@router.callback_query(F.data.startswith("select_group_"), ShowLinkStates.waiting_for_group_selection)
async def process_show_links_selection(callback_query: CallbackQuery):
    group_id = int(callback_query.data.split("_")[2])
    db = AsyncSessionLocal()
    try:
        group = await get_university_group_by_id(db, int(group_id))
        if not group:
            await callback_query.message.edit_text("❌ Группа не найдена.")
            return

        await show_links_list(callback_query.message, group.id, group.name, callback_query.from_user.id)
    finally:
        await db.close()


async def show_links_list(message: Message, group_id: int, group_name: str, admin_id: int):
    db = AsyncSessionLocal()
    try:
        links_data = await get_links_by_owner(db, admin_id, group_id)
        if not links_data:
            await message.answer(
                f"📋 У групі <b>{group_name}</b> поки немає доданих посилань.",
                parse_mode="HTML"
            )
            return

        subjects_dict = {}
        for link in links_data:
            if link.subject.name not in subjects_dict:
                subjects_dict[link.subject.name] = []
            subjects_dict[link.subject.name].append(link)

        text = f"📚 <b>Посилання для групи {group_name}</b>\n\n"

        for subject_name, links in subjects_dict.items():
            text += f"🎓 <b>{subject_name}</b>\n"
            for link in links:
                text += f"{link.name_link} {link.class_type}: {link.meeting_link}\n"
            text += "\n"

        text += "💡 <i>Щоб додати нове посилання, скористайтесь командою /add_link</i>"
        try:
            await message.delete()
        except Exception as e:
            pass
        await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)

    except Exception as e:
        await message.answer(f"Сталася помилка під час отримання списку посилань.\n Напишіть @shallbeewolk")
        logger.error(f"Сталася помилка під час отримання списку посилань:{e}")
    finally:
        await db.close()
