import json
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID  = int(os.getenv("ADMIN_ID"))
API_TOKEN = os.getenv("API_TOKEN")
API_MODEL = os.getenv("API_MODEL")
DATA_FILE = os.getenv("DATA_FILE")
TG_API = int(os.getenv("TG_API"))
TG_HASH = os.getenv("TG_HASH")
SESSIONS_DIR = "sessions"
MAX_TOKENS         = int(os.getenv("MAX_TOKENS", 500))
FREQUENCY_PENALTY  = float(os.getenv("FREQUENCY_PENALTY", 0.4))
PRESENCE_PENALTY   = float(os.getenv("PRESENCE_PENALTY", 0.2))



# ── Базовая структура data.json ───────────────────────────────
DEFAULT_DATA = {
    "bot_enabled": False,
    "accounts": {},
    "roles": []
}


# ── Чтение / запись ───────────────────────────────────────────

def load_data() -> dict:
    if not os.path.exists(DATA_FILE):
        save_data(DEFAULT_DATA)
        return DEFAULT_DATA.copy()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Аккаунты ─────────────────────────────────────────────────

def get_accounts() -> dict:
    return load_data().get("accounts", {})


def get_account(acc_id: str) -> dict | None:
    return get_accounts().get(acc_id)


def create_account(acc_id: str, username: str) -> dict:
    data = load_data()
    data["accounts"][acc_id] = {
        "id":          acc_id,
        "username":    username,
        "users":       {},
        "session_file": f"{SESSIONS_DIR}/{acc_id}.session"
    }
    save_data(data)
    return data["accounts"][acc_id]


def update_account(acc_id: str, **fields) -> None:
    data = load_data()
    if acc_id in data["accounts"]:
        data["accounts"][acc_id].update(fields)
        save_data(data)


def delete_account(acc_id: str) -> None:
    data = load_data()
    data["accounts"].pop(acc_id, None)
    save_data(data)


# ── Пользователи внутри аккаунта ─────────────────────────────

def get_users(acc_id: str) -> dict:
    acc = get_account(acc_id)
    return acc.get("users", {}) if acc else {}


def get_user(acc_id: str, user_id: str) -> dict | None:
    return get_users(acc_id).get(str(user_id))


def create_user(acc_id: str, user_id: int, username: str, name: str) -> dict:
    data = load_data()
    data["accounts"][acc_id]["users"][str(user_id)] = {
        "id":          user_id,
        "username":    username,
        "name":        name,
        "description": "",
        "active":      False,
        "role":        None,
        "context":     "10"
    }
    save_data(data)
    return data["accounts"][acc_id]["users"][str(user_id)]


def update_user(acc_id: str, user_id: str, **fields) -> None:
    data = load_data()
    if user_id in data["accounts"].get(acc_id, {}).get("users", {}):
        data["accounts"][acc_id]["users"][user_id].update(fields)
        save_data(data)


def delete_user(acc_id: str, user_id: str) -> None:
    data = load_data()
    data["accounts"].get(acc_id, {}).get("users", {}).pop(user_id, None)
    save_data(data)


# ── Роли ─────────────────────────────────────────────────────

def get_roles() -> list[dict]:
    return load_data().get("roles", [])


def create_role(key: str, title: str, description: str = "") -> dict:
    data = load_data()
    role = {"key": key, "title": title, "description": description}
    data["roles"].append(role)
    save_data(data)
    return role


def update_role(key: str, **fields) -> None:
    data = load_data()
    for role in data["roles"]:
        if role["key"] == key:
            role.update(fields)
            break
    save_data(data)


def delete_role(key: str) -> None:
    data = load_data()
    data["roles"] = [r for r in data["roles"] if r["key"] != key]
    save_data(data)
