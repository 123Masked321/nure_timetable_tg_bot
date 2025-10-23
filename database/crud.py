from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from sqlalchemy.orm import selectinload
from database.models import UniversityGroup, TelegramChat, ClassLink, PrivateSubscriber
from typing import Optional, List


async def create_university_group(
        db: AsyncSession,
        cist_group_id: int,
        name: str
) -> UniversityGroup:
    """Створити університетську групу"""
    result = await db.execute(
        select(UniversityGroup).where(UniversityGroup.cist_group_id == cist_group_id)
    )
    existing_group = result.scalars().first()

    if existing_group:
        return existing_group

    university_group = UniversityGroup(
        cist_group_id=cist_group_id,
        name=name
    )
    db.add(university_group)
    await db.commit()
    await db.refresh(university_group)
    return university_group


async def get_university_group_by_id(db: AsyncSession, group_id: int) -> Optional[UniversityGroup]:
    """Отримати університетську групу за ID"""
    result = await db.execute(
        select(UniversityGroup).where(UniversityGroup.id == group_id)
    )
    return result.scalars().first()


async def get_university_group_by_cist_id(db: AsyncSession, cist_group_id: int) -> Optional[UniversityGroup]:
    """Отримати університетську групу за CIST ID"""
    result = await db.execute(
        select(UniversityGroup).where(UniversityGroup.cist_group_id == cist_group_id)
    )
    return result.scalars().first()


async def update_university_group(
        db: AsyncSession,
        group_id: int,
        new_name: str,
        new_cist_id: int
) -> Optional[UniversityGroup]:
    """Оновити дані університетської групи"""
    await db.execute(
        update(UniversityGroup)
        .where(UniversityGroup.id == group_id)
        .values(name=new_name, cist_group_id=new_cist_id)
    )
    await db.commit()

    return await get_university_group_by_id(db, group_id)


async def switch_telegram_chat_group(
        db: AsyncSession,
        chat_id: int,
        new_university_group_id: int
) -> Optional[TelegramChat]:
    """
    Переключити Telegram чат на іншу університетську групу
    """
    await db.execute(
        update(TelegramChat)
        .where(TelegramChat.chat_id == chat_id)
        .values(university_group_id=new_university_group_id)
    )
    await db.commit()

    return await get_telegram_chat_by_chat_id(db, chat_id)


async def cleanup_unused_university_groups(db: AsyncSession) -> int:
    """
    Видалити університетські групи, до яких не підключено жодного Telegram чату
    """
    from sqlalchemy import delete

    # Знаходимо групи без чатів
    subquery = select(TelegramChat.university_group_id).distinct()

    result = await db.execute(
        select(UniversityGroup)
        .where(UniversityGroup.id.not_in(subquery))
    )
    unused_groups = result.scalars().all()

    count = len(unused_groups)

    if count > 0:
        await db.execute(
            delete(UniversityGroup)
            .where(UniversityGroup.id.not_in(subquery))
        )
        await db.commit()

    return count


async def get_all_university_groups(db: AsyncSession) -> List[UniversityGroup]:
    """Отримати всі університетські групи"""
    result = await db.execute(select(UniversityGroup))
    return result.scalars().all()


async def get_all_university_groups_by_admin(db: AsyncSession, admin_id: int) -> List[UniversityGroup]:
    """Отримати всі унікальні університетські групи, де користувач є адміністратором"""
    result = await db.execute(
        select(UniversityGroup)
        .join(TelegramChat, TelegramChat.university_group_id == UniversityGroup.id)
        .where(TelegramChat.admin_user_id == admin_id)
        .distinct()
    )
    return result.scalars().all()


async def create_telegram_chat(
        db: AsyncSession,
        chat_id: int,
        university_group_id: int,
        admin_user_id: int,
        admin_username: Optional[str] = None
) -> TelegramChat:
    """Створити Telegram чат і зв'язати з університетською групою"""
    telegram_chat = TelegramChat(
        chat_id=chat_id,
        university_group_id=university_group_id,
        admin_user_id=admin_user_id,
        admin_username=admin_username
    )
    db.add(telegram_chat)
    await db.commit()
    await db.refresh(telegram_chat)
    return telegram_chat


async def get_telegram_chat_by_chat_id(db: AsyncSession, chat_id: int) -> Optional[TelegramChat]:
    """Отримати Telegram чат за chat_id"""
    result = await db.execute(
        select(TelegramChat).where(TelegramChat.chat_id == chat_id)
    )
    return result.scalars().first()


async def get_telegram_chat_id_by_group_id(db: AsyncSession, group_id: int) -> Optional[int]:
    """Получить ID Telegram-чата по ID университетской группы"""

    # Исправлена опечатка в universuty_group_id
    # Выбираем только TelegramChat.id
    result = await db.execute(
        select(TelegramChat.chat_id).where(TelegramChat.university_group_id == group_id)
    )

    # Возвращаем первый найденный ID или None
    return result.scalars().first()


async def get_all_groups(db: AsyncSession) -> List[TelegramChat]:
    """Отримати всі Telegram чати"""
    result = await db.execute(
        select(TelegramChat).options(selectinload(TelegramChat.university_group))
    )
    return result.scalars().all()


async def get_telegram_chats_by_admin(db: AsyncSession, admin_user_id: int) -> List[TelegramChat]:
    """Отримати всі Telegram чати, де користувач є адміном"""
    result = await db.execute(
        select(TelegramChat).where(TelegramChat.admin_user_id == admin_user_id)
    )
    return result.scalars().all()


async def is_group_admin(db: AsyncSession, chat_id: int, user_id: int) -> bool:
    """Перевірити, чи є користувач адміном групи"""
    telegram_chat = await get_telegram_chat_by_chat_id(db, chat_id)
    if telegram_chat and telegram_chat.admin_user_id == user_id:
        return True
    return False


async def get_private_subscriber(
        db: AsyncSession,
        user_id: int,
        chat_id: int
) -> Optional[PrivateSubscriber]:
    """Отримати підписника за user_id і chat_id"""
    result = await db.execute(
        select(PrivateSubscriber).where(
            PrivateSubscriber.user_id == user_id,
            PrivateSubscriber.chat_id == chat_id
        )
    )
    return result.scalars().first()


async def add_private_subscriber(
        db: AsyncSession,
        user_id: int,
        chat_id: int,
        username: Optional[str] = None
) -> bool:
    """Додати користувача до списку приватних підписників"""
    result = await get_private_subscriber(db, user_id, chat_id)
    if result:
        return False

    subscriber = PrivateSubscriber(
        user_id=user_id,
        chat_id=chat_id,
        username=username
    )
    db.add(subscriber)
    await db.commit()
    await db.refresh(subscriber)
    return True


async def get_private_subscribers_by_chat(
        db: AsyncSession,
        chat_id: int
) -> List[PrivateSubscriber]:
    """Отримати всіх підписників певного Telegram чату"""
    result = await db.execute(
        select(PrivateSubscriber).where(PrivateSubscriber.chat_id == chat_id)
    )
    return result.scalars().all()


async def remove_private_subscriber(
        db: AsyncSession,
        user_id: int,
        chat_id: int
) -> bool:
    """Видалити користувача зі списку приватних підписників"""
    subscriber = await get_private_subscriber(db, user_id, chat_id)
    if subscriber:
        await db.delete(subscriber)
        await db.commit()
        return True

    return False