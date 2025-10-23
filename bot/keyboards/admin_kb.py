from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from typing import List
from database.models import UniversityGroup, ClassLink


TYPE_CLASSES = [
    ("Лекція", "Лк"),
    ("Практична", "Пз"),
    ("Лабораторна", "Лб"),
    ("Консультація", "Конс"),
    ("Залік/екзамен", "Екз")
]


def build_action_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Створити нове посилання", callback_data="select_action_add")],
        [InlineKeyboardButton(text="Редагувати існуюче посилання", callback_data="select_action_edit")],
        [InlineKeyboardButton(text="Видалити існуюче посилання", callback_data="select_action_delete")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_groups_keyboard(groups: List[UniversityGroup]) -> InlineKeyboardMarkup:
    buttons = []
    for group in groups:
        buttons.append(
            [InlineKeyboardButton(text=group.name, callback_data=f"select_group_{group.id}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_subjects_keyboard(subjects: List[str]) -> InlineKeyboardMarkup:
    buttons = []
    for subject in subjects:
        buttons.append(
            [InlineKeyboardButton(text=subject.name, callback_data=f"select_subject_{subject.id}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_type_class_keyboard(selected_types: list[str] = None) -> InlineKeyboardMarkup:
    if selected_types is None:
        selected_types = []

    buttons = []
    for name, code in TYPE_CLASSES:
        text = f"{"✅ " if code in selected_types else "☐"}{name}"
        buttons.append([InlineKeyboardButton(text=f"{text}", callback_data=f"select_type_{code}")])

    # Кнопка подтверждения выбора
    buttons.append([InlineKeyboardButton(text="Готово", callback_data="select_type_done")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_links_list_keyboard(links: List["ClassLink"], selected_links: list[int | str] | None = None) -> InlineKeyboardMarkup:
    if selected_links is None:
        selected_links = []

    buttons = []
    for link in links:
        checked = "✅ " if int(link.id) in selected_links else "☐ "
        text = f"{checked}{link.name_link}({link.class_type})"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"select_link_{link.id}")])

    buttons.append([InlineKeyboardButton(text="Готово", callback_data="select_link_done")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_skip_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Пропустити")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )