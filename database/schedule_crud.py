from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from database.models import ScheduleClass, ClassLink, Subject
from typing import List, Optional
from datetime import date, time as dt_time


async def create_schedule_class(
        db: AsyncSession,
        university_group_id: int,
        subject_id: int,
        date_obj: date,
        day_of_week: str,
        time_start: dt_time,
        time_end: dt_time,
        subject_name: str,
        subject_brief: str = None,
        class_type: str = None,
        auditory: str = None,
        lector: str = None,
) -> ScheduleClass:
    """Додати пару в розклад"""
    schedule = ScheduleClass(
        university_group_id=university_group_id,
        subject_id=subject_id,
        date=date_obj,
        day_of_week=day_of_week,
        time_start=time_start,
        time_end=time_end,
        subject_name=subject_name,
        subject_brief=subject_brief,
        class_type=class_type,
        auditory=auditory,
        lector=lector.strip()
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return schedule


async def get_schedule_for_date(
        db: AsyncSession,
        university_group_id: int,
        date_obj: date
) -> List[ScheduleClass]:
    """Отримати розклад на день"""
    result = await db.execute(
        select(ScheduleClass)
        .where(ScheduleClass.university_group_id == university_group_id, ScheduleClass.date == date_obj)
        .order_by(ScheduleClass.time_start)
    )
    return result.scalars().all()


async def get_schedule_for_week(
        db: AsyncSession,
        university_group_id: int,
        start_date: date,
        end_date: date
) -> List[ScheduleClass]:
    """Отримати розклад на неділю"""
    result = await db.execute(
        select(ScheduleClass)
        .where(
            ScheduleClass.university_group_id == university_group_id,
            ScheduleClass.date.between(start_date, end_date)
        )
        .order_by(ScheduleClass.date, ScheduleClass.time_start)
    )
    return result.scalars().all()


async def get_class_at_time(
        db: AsyncSession,
        university_group_id: int,
        date_obj: date,
        time_start: dt_time
) -> Optional[ScheduleClass]:
    """Отримати пару у певний час"""
    result = await db.execute(
        select(ScheduleClass)
        .where(
            ScheduleClass.university_group_id == university_group_id,
            ScheduleClass.date == date_obj,
            ScheduleClass.time_start == time_start
        )
    )
    return result.scalars().first()


async def delete_old_schedule(
        db: AsyncSession,
        university_group_id: int,
        before_date: date
) -> bool:
    """Удалили старий розклад(за часом)"""
    try:
        await db.execute(
            delete(ScheduleClass)
            .where(ScheduleClass.university_group_id == university_group_id, ScheduleClass.date < before_date)
        )
        await db.commit()
        return True
    except Exception as e:
        await db.rollback()
        return False


async def clear_group_schedule(
        db: AsyncSession,
        university_group_id: int
) -> bool:
    """Удалити увесь розклад"""
    try:
        await db.execute(
            delete(ScheduleClass).where(ScheduleClass.university_group_id == university_group_id)
        )
        await db.commit()
        return True
    except Exception:
        await db.rollback()
        return False


async def create_subject_for_group(
        db: AsyncSession,
        group_id: int,
        name: str,
        brief: str
) -> Subject:
    subject = Subject(
        name=name.strip(),
        brief=brief.strip(),
        university_group_id=group_id,
    )
    db.add(subject)
    await db.flush()
    return subject


async def get_subjects_for_group(
        db: AsyncSession,
        group_id: int
) -> List[Subject]:
    """
    Отримати список предметів групи
    """
    result = await db.execute(
        select(Subject)
        .where(Subject.university_group_id == group_id)
        .order_by(Subject.name)
    )
    return result.scalars().all()


async def get_subject_by_name(
    db: AsyncSession,
    group_id: int,
    subject_name: str,
) -> Optional[Subject]:
    """
    Отримати предмет для групи за ім'ям
    """
    query = (
        select(Subject)
        .where(Subject.university_group_id == group_id)
        .where(Subject.name == subject_name)
        .limit(1)
    )

    result = await db.execute(query)
    return result.scalars().first()


async def get_subject_by_id(
        db: AsyncSession,
        subject_id: int
) -> Optional[Subject]:
    """Отримати предмет за айді"""
    result = await db.execute(select(Subject).where(Subject.id == subject_id))
    return result.scalars().first()


async def delete_subject_by_id(
        db: AsyncSession,
        subject_id: int
) -> bool:
    """Видалити предмет по айді"""
    subject = await get_subject_by_id(db, subject_id)
    if subject:
        await db.delete(subject)
        await db.commit()
        return True

    return False


async def create_link_for_subject(
        db: AsyncSession,
        university_group_id: int,
        subject_id: int,
        owner_user_id: int,
        class_type: str = None,
        name_link: str = None,
        meeting_link: str = None
) -> ClassLink:
    """
    Додати посилання
    """
    link = ClassLink(
        university_group_id=university_group_id,
        subject_id=subject_id,
        owner_user_id=owner_user_id,
        class_type=class_type,
        name_link=name_link,
        meeting_link=meeting_link
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


async def get_links_for_subject(
        db: AsyncSession,
        university_group_id: int,
        subject_id: int,
        class_type: str,
        owner_user_id: int,
) -> List[ClassLink]:
    """ Отримати посилання для предмету """
    query = select(ClassLink).where(
        ClassLink.university_group_id == university_group_id,
        ClassLink.subject_id == subject_id,
        ClassLink.class_type == class_type,
        ClassLink.owner_user_id == owner_user_id,
    )
    result = await db.execute(query)
    return result.scalars().all()


async def get_links_by_group(
        db: AsyncSession,
        university_group_id: int
) -> List[ClassLink]:
    """Отримати всі посилання для університетської групи"""
    result = await db.execute(
        select(ClassLink).where(ClassLink.university_group_id == university_group_id)
    )
    return result.scalars().all()


async def get_links_by_owner(
        db: AsyncSession,
        owner_user_id: int,
        university_group_id: int,
) -> List[ClassLink]:
    """ Отримати посилання адміністратора """
    query = (
        select(ClassLink)
        .options(selectinload(ClassLink.subject))  # Предзагружаем subject
        .where(
            ClassLink.owner_user_id == owner_user_id,
            ClassLink.university_group_id == university_group_id
        )
    )

    result = await db.execute(query)
    return result.scalars().all()


async def get_link_by_id(
        db: AsyncSession,
        link_id: int,
) -> Optional[ClassLink]:
    """ Отримати посилання за айді """
    result = await db.execute(select(ClassLink).where(ClassLink.id == link_id))
    return result.scalars().first()


async def update_link(
        db: AsyncSession,
        link_id: int,
        name_link: str = None,
        meeting_link: str = None,
) -> Optional[ClassLink]:
    """ Обновити посилання """
    link = await get_link_by_id(db, link_id)
    if link:
        if meeting_link is not None:
            link.meeting_link = meeting_link
        if name_link is not None:
            link.name_link = name_link
        await db.commit()
        await db.refresh(link)
    return link


async def delete_link(
        db: AsyncSession,
        link_id: int
) -> bool:
    """ Удалити посилання """
    link = await get_link_by_id(db, link_id)
    if link:
        await db.delete(link)
        await db.commit()
        return True
    return False
