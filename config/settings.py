import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

SCHEDULE_API_URL = os.getenv("SCHEDULE_API_URL")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL не установлен в .env файле")

TIMEZONE = os.getenv("TIMEZONE", "Europe/Kyiv")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")