import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
_chat_id_raw = os.getenv("TELEGRAM_CHAT_ID", "0")
TELEGRAM_CHAT_ID: int = int(_chat_id_raw) if _chat_id_raw.lstrip("-").isdigit() else 0
DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
LEARNING_LANGUAGE: str = os.getenv("LEARNING_LANGUAGE", "Mandarin Chinese")
DB_PATH: str = os.getenv("DB_PATH", "tutor.db")
_notif_hour_raw = os.getenv("NOTIFICATION_HOUR", "22")
NOTIFICATION_HOUR: int = int(_notif_hour_raw) if _notif_hour_raw.isdigit() else 22
_notif_min_raw = os.getenv("NOTIFICATION_MINUTE", "0")
NOTIFICATION_MINUTE: int = int(_notif_min_raw) if _notif_min_raw.isdigit() else 0
NOTIFICATION_TIMEZONE: str = os.getenv("NOTIFICATION_TIMEZONE", "Europe/London")


def validate() -> None:
    missing = [k for k, v in {
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "DEEPSEEK_API_KEY": DEEPSEEK_API_KEY,
    }.items() if not v]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")
