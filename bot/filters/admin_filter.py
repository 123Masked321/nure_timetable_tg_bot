from aiogram.filters import Filter
from aiogram.types import Message
from database.database import AsyncSessionLocal
from database.crud import is_group_admin, get_telegram_chat_by_chat_id


class IsGroupAdmin(Filter):
    async def __call__(self, message: Message) -> bool:
        if message.chat.type == "private":
            await message.answer("❌ Ця команда працює лише в групових чатах")
            return False

        chat_id = int(message.chat.id)
        user_id = message.from_user.id

        db = AsyncSessionLocal()
        try:
            group = await get_telegram_chat_by_chat_id(db, chat_id)

            if not group:
                return False

            if not await is_group_admin(db, chat_id, user_id):
                await message.answer("❌ Тільки адміністратор може використовувати цю команду")
                return False

            return True
        finally:
            await db.close()
