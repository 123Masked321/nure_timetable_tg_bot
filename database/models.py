from sqlalchemy import (
    Column, Integer, String, ForeignKey, DateTime, Date, Time, Index, BigInteger
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
from zoneinfo import ZoneInfo
from config.settings import TIMEZONE

KYIV_TZ = ZoneInfo(TIMEZONE)
Base = declarative_base()


class UniversityGroup(Base):
    __tablename__ = "university_groups"

    id = Column(Integer, primary_key=True)
    cist_group_id = Column(Integer, unique=True, nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    subjects = relationship("Subject", back_populates="university_group", cascade="all, delete-orphan")
    telegram_chats = relationship("TelegramChat", back_populates="university_group", cascade="all, delete-orphan")
    schedule = relationship("ScheduleClass", back_populates="university_group", cascade="all, delete-orphan")
    links = relationship("ClassLink", back_populates="university_group", cascade="all, delete-orphan")


class TelegramChat(Base):
    __tablename__ = "telegram_chats"

    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, unique=True, nullable=False)
    admin_user_id = Column(BigInteger, nullable=False)
    admin_username = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    university_group_id = Column(Integer, ForeignKey("university_groups.id", ondelete="CASCADE"), nullable=False)
    university_group = relationship("UniversityGroup", back_populates="telegram_chats")
    private_subscribers = relationship("PrivateSubscriber", back_populates="chat", cascade="all, delete-orphan")


class PrivateSubscriber(Base):
    __tablename__ = "private_subscribers"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    username = Column(String, nullable=True)
    chat_id = Column(BigInteger, ForeignKey("telegram_chats.chat_id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    chat = relationship("TelegramChat", back_populates="private_subscribers")

    __table_args__ = (
        Index("ix_private_user_chat", "user_id", "chat_id", unique=True),
    )


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True)
    brief = Column(String, nullable=False)
    name = Column(String, nullable=False)
    university_group_id = Column(Integer, ForeignKey("university_groups.id", ondelete="CASCADE"), nullable=True)

    university_group = relationship("UniversityGroup", back_populates="subjects")
    schedule_classes = relationship("ScheduleClass", back_populates="subject", cascade="all, delete-orphan")
    links = relationship("ClassLink", back_populates="subject", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Subject(id={self.id}, name='{self.name}', brief='{self.brief}', group_id={self.university_group_id})>"


class ScheduleClass(Base):
    __tablename__ = "schedule_classes"

    id = Column(Integer, primary_key=True)
    university_group_id = Column(Integer, ForeignKey("university_groups.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    date = Column(Date, nullable=False)
    day_of_week = Column(String, nullable=False)
    time_start = Column(Time, nullable=False)
    time_end = Column(Time, nullable=False)
    subject_name = Column(String, nullable=False)
    subject_brief = Column(String)
    class_type = Column(String)
    auditory = Column(String)
    lector = Column(String)

    university_group = relationship("UniversityGroup", back_populates="schedule")
    subject = relationship("Subject", back_populates="schedule_classes")

    __table_args__ = (
        Index('ix_uni_group_date', 'university_group_id', 'date'),
        Index('ix_subject_id', 'subject_id'),
    )


class ClassLink(Base):
    __tablename__ = "class_links"

    id = Column(Integer, primary_key=True)
    university_group_id = Column(Integer, ForeignKey("university_groups.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    class_type = Column(String, nullable=True)
    owner_user_id = Column(Integer, nullable=False)
    name_link = Column(String)
    meeting_link = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    university_group = relationship("UniversityGroup", back_populates="links")
    subject = relationship("Subject", back_populates="links")

    __table_args__ = (
        Index(
            'ix_links_per_group_subject_type',
            'university_group_id',
            'subject_id',
            'class_type'
        ),
    )