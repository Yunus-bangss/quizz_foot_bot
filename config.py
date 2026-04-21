import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    load_dotenv()


def to_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        raise ValueError(
            f"La variable d'environnement '{name}' est manquante. "
            f"Ajoute-la dans le fichier .env."
        )
    return value.strip()


class Config:
    BOT_TOKEN = require_env("BOT_TOKEN")
    PREFIX = os.getenv("BOT_PREFIX", "!")
    DEBUG = to_bool(os.getenv("DEBUG", "false"))

    GUILD_ID = to_int(os.getenv("GUILD_ID"), 0)
    OWNER_ID = to_int(os.getenv("OWNER_ID"), 0)
    ADMIN_ROLE_ID = to_int(os.getenv("ADMIN_ROLE_ID"), 0)
    MOD_ROLE_ID = to_int(os.getenv("MOD_ROLE_ID"), 0)

    DEFAULT_EMBED_COLOR = int(os.getenv("DEFAULT_EMBED_COLOR", "65280"))
    ERROR_EMBED_COLOR = int(os.getenv("ERROR_EMBED_COLOR", "16711680"))
    SUCCESS_EMBED_COLOR = int(os.getenv("SUCCESS_EMBED_COLOR", "32768"))
    WARNING_EMBED_COLOR = int(os.getenv("WARNING_EMBED_COLOR", "16753920"))

    MAX_QUESTIONS_PER_MATCH = to_int(os.getenv("MAX_QUESTIONS_PER_MATCH", "5"), 5)
    QUESTION_TIMEOUT = to_int(os.getenv("QUESTION_TIMEOUT", "10"), 10)
    DAILY_TIMEOUT = to_int(os.getenv("DAILY_TIMEOUT", "15"), 15)
    VAR_TIMEOUT = to_int(os.getenv("VAR_TIMEOUT", "15"), 15)
    CHALLENGE_TIMEOUT = to_int(os.getenv("CHALLENGE_TIMEOUT", "300"), 300)

    DATA_DIR = BASE_DIR / "data"
    LOGS_DIR = BASE_DIR / "logs"

    ENABLE_MESSAGE_COMMANDS = to_bool(os.getenv("ENABLE_MESSAGE_COMMANDS", "true"))
    ENABLE_SLASH_COMMANDS = to_bool(os.getenv("ENABLE_SLASH_COMMANDS", "true"))

    @classmethod
    def validate(cls):
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN est vide.")

        if cls.MAX_QUESTIONS_PER_MATCH <= 0:
            raise ValueError("MAX_QUESTIONS_PER_MATCH doit être supérieur à 0.")

        if cls.QUESTION_TIMEOUT <= 0:
            raise ValueError("QUESTION_TIMEOUT doit être supérieur à 0.")

        if cls.DAILY_TIMEOUT <= 0:
            raise ValueError("DAILY_TIMEOUT doit être supérieur à 0.")

        if cls.VAR_TIMEOUT <= 0:
            raise ValueError("VAR_TIMEOUT doit être supérieur à 0.")

        if cls.CHALLENGE_TIMEOUT <= 0:
            raise ValueError("CHALLENGE_TIMEOUT doit être supérieur à 0.")

        cls.DATA_DIR.mkdir(exist_ok=True)
        cls.LOGS_DIR.mkdir(exist_ok=True)

    @classmethod
    def is_admin_role(cls, role_id: int) -> bool:
        if not role_id:
            return False
        return role_id in {cls.ADMIN_ROLE_ID, cls.MOD_ROLE_ID}

    @classmethod
    def summary(cls):
        return {
            "debug": cls.DEBUG,
            "prefix": cls.PREFIX,
            "guild_id": cls.GUILD_ID,
            "owner_id": cls.OWNER_ID,
            "admin_role_id": cls.ADMIN_ROLE_ID,
            "mod_role_id": cls.MOD_ROLE_ID,
            "max_questions_per_match": cls.MAX_QUESTIONS_PER_MATCH,
            "question_timeout": cls.QUESTION_TIMEOUT,
            "daily_timeout": cls.DAILY_TIMEOUT,
            "var_timeout": cls.VAR_TIMEOUT,
            "challenge_timeout": cls.CHALLENGE_TIMEOUT,
            "enable_message_commands": cls.ENABLE_MESSAGE_COMMANDS,
            "enable_slash_commands": cls.ENABLE_SLASH_COMMANDS,
            "data_dir": str(cls.DATA_DIR),
            "logs_dir": str(cls.LOGS_DIR),
        }


Config.validate()