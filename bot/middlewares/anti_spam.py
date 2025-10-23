import time

from aiogram import BaseMiddleware
from aiogram.types import Message


class AntiSpamMiddleware(BaseMiddleware):
    def __init__(self, delay: int = 3):
        super().__init__()
        self.delay = delay
        self.last_time = {}

    async def __call__(self, handler, event: Message, data):
        user_id = event.from_user.id
        now = time.time()

        if user_id in self.last_time and now - self.last_time[user_id] < self.delay:
            await event.answer("🚫 Занадто швидко! Зачекай трохи перед новою командою.")
            return

        self.last_time[user_id] = now
        return await handler(event, data)