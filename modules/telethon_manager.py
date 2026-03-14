import logging
import os
from telethon import TelegramClient
from config import TG_API, TG_HASH, get_accounts, update_account
from modules.listeners import register_listener

logger = logging.getLogger(__name__)

active_clients: dict[str, TelegramClient] = {}


async def connect_account(acc_id: str, session_file: str) -> bool:
    if not os.path.exists(session_file):
        logger.warning(f"Сессия не найдена: {session_file}")
        return False
    try:
        client = TelegramClient(session_file, int(TG_API), TG_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            logger.warning(f"Аккаунт {acc_id} не авторизован.")
            await client.disconnect()
            return False
        active_clients[acc_id] = client
        register_listener(client, acc_id) 
        logger.info(f"Аккаунт {acc_id} подключён и слушает сообщения.")
        return True
    except Exception as e:
        logger.error(f"Ошибка подключения {acc_id}: {e}")
        return False


async def disconnect_account(acc_id: str) -> None:
    """Отключить клиент из памяти."""
    client = active_clients.pop(acc_id, None)
    if client:
        try:
            await client.disconnect()
            logger.info(f"Аккаунт {acc_id} отключён.")
        except Exception as e:
            logger.warning(f"Ошибка отключения {acc_id}: {e}")


async def connect_all_accounts() -> None:
    """Вызывается при старте бота — подключает все аккаунты из data.json."""
    accounts = get_accounts()
    if not accounts:
        logger.info("Нет подключённых аккаунтов.")
        return
    for acc_id, acc in accounts.items():
        session_file = acc.get("session_file", "")
        ok = await connect_account(acc_id, session_file)
        if not ok:
            # Помечаем как неактивный если сессия битая
            update_account(acc_id, enabled=False)


async def disconnect_all_accounts() -> None:
    for acc_id in list(active_clients.keys()):
        await disconnect_account(acc_id)


def get_client(acc_id: str) -> TelegramClient | None:
    return active_clients.get(acc_id)


def is_connected(acc_id: str) -> bool:
    client = active_clients.get(acc_id)
    return client is not None and client.is_connected()
