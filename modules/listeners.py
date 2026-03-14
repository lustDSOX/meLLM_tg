import asyncio
import logging
from telethon import events
from telethon import TelegramClient

from config import load_data, get_user, get_roles
from modules.openrouter import ask

logger = logging.getLogger(__name__)

# ── Буфер входящих сообщений и дебаунс-задачи ────────────────
# Ключ: (acc_id, user_tg_id)
_pending_messages: dict[tuple, list[str]] = {}
_pending_tasks:    dict[tuple, asyncio.Task] = {}

DEBOUNCE_SECONDS = 4    # ждём паузу после последнего сообщения
TYPING_WAIT      = 8    # максимум ждём печатание


# ══════════════════════════════════════════════════════════════
#  РЕГИСТРАЦИЯ ХЕНДЛЕРОВ НА КЛИЕНТ
# ══════════════════════════════════════════════════════════════

def register_listener(client: TelegramClient, acc_id: str) -> None:
    """Вызывается из telethon_manager после успешного connect_account."""

    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
    async def on_message(event):
        data = load_data()

        # Глобальный рубильник
        if not data.get("bot_enabled", True):
            return

        acc = data["accounts"].get(acc_id)
        if not acc or not acc.get("enabled", True):
            return

        sender_id = str(event.sender_id)
        user = get_user(acc_id, sender_id)

        # Пользователь не добавлен или выключен
        if not user or not user.get("active", False):
            return

        text = event.message.message.strip()
        if not text:
            return

        key = (acc_id, sender_id)

        # Добавляем сообщение в буфер
        _pending_messages.setdefault(key, []).append(text)

        # Сбрасываем таймер дебаунса
        if key in _pending_tasks:
            _pending_tasks[key].cancel()

        _pending_tasks[key] = asyncio.create_task(
            _debounce_and_reply(client, acc_id, sender_id, event.sender_id, user)
        )


async def _debounce_and_reply(
    client: TelegramClient,
    acc_id: str,
    sender_id: str,
    sender_tg_id: int,
    user: dict
) -> None:
    key = (acc_id, sender_id)

    # Шаг 1: ждём паузу в сообщениях
    await asyncio.sleep(DEBOUNCE_SECONDS)

    # Шаг 2: проверяем не печатает ли пользователь
    typing_deadline = asyncio.get_event_loop().time() + TYPING_WAIT
    while asyncio.get_event_loop().time() < typing_deadline:
        if await _is_typing(client, sender_tg_id):
            await asyncio.sleep(2)
        else:
            break

    # Шаг 3: собираем накопленные сообщения
    buffered = _pending_messages.pop(key, [])
    _pending_tasks.pop(key, None)

    if not buffered:
        return

    # Объединяем несколько коротких сообщений в одно
    combined_input = "\n".join(buffered)

    # Шаг 4: собираем контекст из истории
    context_size = int(user.get("context", "10"))
    messages = await _build_context(client, sender_tg_id, context_size, combined_input)

    # Шаг 5: получаем системный промпт роли
    system_prompt, temp_key = _get_role(user.get("role"))

    # Шаг 6: запрос к OpenRouter
    logger.info(f"[{acc_id}] Запрос к OpenRouter для user {sender_id}")
    response = await ask(system_prompt=system_prompt, messages=messages, temperature_key=temp_key)

    if not response:
        logger.warning(f"[{acc_id}] Пустой ответ от OpenRouter")
        return

    # Шаг 7: отправляем ответ с пометкой
    final_text = f"{response}\n\n@bot"
    await client.send_message(sender_tg_id, final_text)
    logger.info(f"[{acc_id}] Ответ отправлен → {sender_id}")


# ══════════════════════════════════════════════════════════════
#  ВСПОМОГАТЕЛЬНЫЕ
# ══════════════════════════════════════════════════════════════

async def _is_typing(client: TelegramClient, user_tg_id: int) -> bool:
    """Проверяем статус печатания через UserUpdate."""
    try:
        async with client.action(user_tg_id, "cancel"):
            pass
        # Запрашиваем последние действия пользователя
        result = await client(
            __import__("telethon.tl.functions.users", fromlist=["GetFullUserRequest"])
            .GetFullUserRequest(user_tg_id)
        )
        # Telethon не предоставляет прямой флаг "печатает"
        # Используем статус online как косвенный признак активности
        status = result.users[0].status if result.users else None
        if status is None:
            return False
        from telethon.tl.types import UserStatusOnline
        return isinstance(status, UserStatusOnline)
    except Exception:
        return False


async def _build_context(
    client: TelegramClient,
    user_tg_id: int,
    context_size: int,
    current_input: str
) -> list[dict]:
    """
    Собирает историю диалога в формате OpenRouter messages.
    Формат: Собеседник → role:user, Ты → role:assistant
    """
    messages = []

    if context_size > 0:
        try:
            history = await client.get_messages(user_tg_id, limit=context_size + 1)
            # history[0] — самое свежее, разворачиваем к хронологии
            history = list(reversed(history))
            me = await client.get_me()

            for msg in history:
                if not msg.message:
                    continue
                if msg.sender_id == me.id:
                    # Убираем метку @bot из истории чтобы не путать модель
                    text = msg.message.replace("\n\n@bot", "").strip()
                    messages.append({"role": "assistant", "content": text})
                else:
                    messages.append({"role": "user", "content": msg.message})
        except Exception as e:
            logger.warning(f"Ошибка получения истории: {e}")

    # Текущий пакет сообщений добавляем последним
    messages.append({"role": "user", "content": current_input})
    return messages



def _get_role(role_key: str | None) -> tuple[str, str]:
    """Возвращает (system_prompt, temperature_key)."""
    default = ("Ты — вежливый помощник. Отвечай естественно и по делу.", "balanced")
    if not role_key:
        return default
    role = next((r for r in get_roles() if r["key"] == role_key), None)
    if not role or not role.get("description"):
        return default
    return role["description"], role.get("temperature", "balanced")