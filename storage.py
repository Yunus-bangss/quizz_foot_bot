import json
import shutil
import threading
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent

_data_lock = threading.RLock()
DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = DATA_DIR / "backups"

MAIN_DATA_FILE = DATA_DIR / "data.json"

OLD_QUIZ_DATA_FILE = DATA_DIR / "quiz_foot_data.json"
OLD_QUESTIONS_FILE = DATA_DIR / "quiz_foot_questions.json"
OLD_SEASONS_FILE = DATA_DIR / "seasons_data.json"
OLD_TOURNAMENTS_FILE = DATA_DIR / "tournaments_data.json"


DEFAULT_DATA = {
    "players": {},
    "questions": [],
    "tournaments": {},
    "seasons": {},
    "matches": {},
    "achievements": {}
}


def ensure_data_dirs():
    DATA_DIR.mkdir(exist_ok=True)
    BACKUP_DIR.mkdir(exist_ok=True)


def ensure_data_files():
    ensure_data_dirs()
    if not MAIN_DATA_FILE.exists():
        initialize_data_file()

ensure_data_files()


def deep_copy_default():
    return {
        "players": {},
        "questions": [],
        "tournaments": {},
        "seasons": {},
        "matches": {},
        "achievements": {}
    }


def create_backup(file_path: Path):
    if not file_path.exists():
        return

    ensure_data_dirs()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{file_path.stem}_{timestamp}.bak.json"
    shutil.copy(file_path, backup_path)


def read_json_file(file_path: Path, default=None):
    if default is None:
        default = {}

    if not file_path.exists():
        return default

    try:
        with file_path.open("r", encoding="utf-8") as f:
            content = f.read()
            if not content.strip():
                return None
            return json.loads(content)
    except (json.JSONDecodeError, OSError):  # FIX: supprimé le doublon json.JSONDecodeError
        return default


def write_json_atomic(file_path: Path, data):
    ensure_data_dirs()
    tmp_file = file_path.with_suffix(file_path.suffix + ".tmp")

    with _data_lock:
        with tmp_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        tmp_file.replace(file_path)


def normalize_data(data):
    clean = deep_copy_default()

    if not isinstance(data, dict):
        return clean

    for key, default_value in clean.items():
        value = data.get(key, default_value)

        if isinstance(default_value, dict):
            clean[key] = value if isinstance(value, dict) else {}
        elif isinstance(default_value, list):
            clean[key] = value if isinstance(value, list) else []
        else:
            clean[key] = value

    return clean


def merge_old_files():
    merged = deep_copy_default()

    old_quiz_data = read_json_file(OLD_QUIZ_DATA_FILE, {})
    old_questions = read_json_file(OLD_QUESTIONS_FILE, [])
    old_seasons = read_json_file(OLD_SEASONS_FILE, {})
    old_tournaments = read_json_file(OLD_TOURNAMENTS_FILE, {})

    if isinstance(old_quiz_data, dict):
        if "players" in old_quiz_data and isinstance(old_quiz_data["players"], dict):
            merged["players"] = old_quiz_data["players"]
        else:
            merged["players"] = old_quiz_data

        if "achievements" in old_quiz_data and isinstance(old_quiz_data["achievements"], dict):
            merged["achievements"] = old_quiz_data["achievements"]

        if "matches" in old_quiz_data and isinstance(old_quiz_data["matches"], dict):
            merged["matches"] = old_quiz_data["matches"]

    if isinstance(old_questions, list):
        merged["questions"] = old_questions
    elif isinstance(old_questions, dict) and "questions" in old_questions:
        merged["questions"] = old_questions["questions"] if isinstance(old_questions["questions"], list) else []

    if isinstance(old_seasons, dict):
        merged["seasons"] = old_seasons

    if isinstance(old_tournaments, dict):
        merged["tournaments"] = old_tournaments

    return normalize_data(merged)


def initialize_data_file():
    ensure_data_dirs()

    if MAIN_DATA_FILE.exists():
        data = read_json_file(MAIN_DATA_FILE, None)
        if data is not None and isinstance(data, dict) and data.get("questions"):
            clean_data = normalize_data(data)
            if clean_data != data:
                create_backup(MAIN_DATA_FILE)
                write_json_atomic(MAIN_DATA_FILE, clean_data)
            return clean_data

    merged_data = merge_old_files()
    write_json_atomic(MAIN_DATA_FILE, merged_data)
    return merged_data


def load_data():
    ensure_data_dirs()

    with _data_lock:
        if not MAIN_DATA_FILE.exists():
            return initialize_data_file()

        data = read_json_file(MAIN_DATA_FILE, deep_copy_default())
        return normalize_data(data)


def save_data(data):
    ensure_data_dirs()

    with _data_lock:
        clean_data = normalize_data(data)

        if MAIN_DATA_FILE.exists():
            create_backup(MAIN_DATA_FILE)

        write_json_atomic(MAIN_DATA_FILE, clean_data)


def get_section(section_name):
    data = load_data()
    return data.get(section_name)


def save_section(section_name, value):
    data = load_data()
    data[section_name] = value
    save_data(data)


def load_players():
    return get_section("players") or {}


def save_players(players):
    save_section("players", players)


def load_questions():
    questions = get_section("questions")
    if not isinstance(questions, list):
        return []
    return questions


def load_questions_safe():
    questions = load_questions()
    return [q for q in questions if isinstance(q, dict) and q.get("question") and q.get("answer")]


def save_questions(questions):
    if not isinstance(questions, list):
        questions = []
    save_section("questions", questions)


def load_tournaments():
    return get_section("tournaments") or {}


def save_tournaments(tournaments):
    save_section("tournaments", tournaments)


def load_seasons():
    return get_section("seasons") or {}


def save_seasons(seasons):
    save_section("seasons", seasons)


def load_matches():
    return get_section("matches") or {}


def save_matches(matches):
    save_section("matches", matches)


def load_achievements():
    return get_section("achievements") or {}


def save_achievements(achievements):
    save_section("achievements", achievements)
