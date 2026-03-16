import asyncio
import logging
from telethon import events
from telethon import TelegramClient

from config import load_data, get_user, get_roles
from modules.openrouter import ask

logger = logging.getLogger(__name__)

_pending_messages: dict[tuple, list[str]] = {}
_pending_tasks:    dict[tuple, asyncio.Task] = {}

# Храним время последнего typing-события: { (acc_id, sender_id): timestamp }
_last_typing:      dict[tuple, float] = {}

DEBOUNCE_SECONDS = 3    # пауза после последнего сообщения
TYPING_TIMEOUT   = 7    # максимум ждём печатание
TYPING_GRACE     = 1.5  # считаем "всё ещё печатает" если typing был < N сек назад


def register_listener(client: TelegramClient, acc_id: str) -> None:

    # ── Слушаем новые сообщения ───────────────────────────────
    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
    async def on_message(event):
        data = load_data()
        if not data.get("bot_enabled", True):
            return

        acc = data["accounts"].get(acc_id)
        if not acc or not acc.get("enabled", True):
            return

        sender_id = str(event.sender_id)
        user = get_user(acc_id, sender_id)
        if not user or not user.get("active", False):
            return

        text = event.message.message.strip()
        if not text:
            return

        key = (acc_id, sender_id)
        _pending_messages.setdefault(key, []).append(text)

        # Сбрасываем дебаунс-таймер
        if key in _pending_tasks:
            _pending_tasks[key].cancel()

        _pending_tasks[key] = asyncio.create_task(
            _debounce_and_reply(client, acc_id, sender_id, event.sender_id, user)
        )

    # ── Слушаем typing-события ────────────────────────────────
    @client.on(events.UserUpdate())
    async def on_user_update(event):
        # typing=True означает что пользователь печатает прямо сейчас
        if not event.typing:
            return

        sender_id = str(event.user_id)
        key = (acc_id, sender_id)

        # Обновляем метку времени только если этот пользователь у нас в очереди
        if key in _pending_tasks:
            _last_typing[key] = asyncio.get_event_loop().time()
            logger.debug(f"[{acc_id}] Пользователь {sender_id} печатает...")


async def _debounce_and_reply(
    client: TelegramClient,
    acc_id: str,
    sender_id: str,
    sender_tg_id: int,
    user: dict
) -> None:
    key = (acc_id, sender_id)

    # Шаг 1: базовая пауза после последнего сообщения
    await asyncio.sleep(DEBOUNCE_SECONDS)

    # Шаг 2: ждём пока пользователь не перестанет печатать
    deadline = asyncio.get_event_loop().time() + TYPING_TIMEOUT
    while asyncio.get_event_loop().time() < deadline:
        last = _last_typing.get(key, 0)
        since_typing = asyncio.get_event_loop().time() - last
        if since_typing < TYPING_GRACE:
            # Недавно было typing-событие — ждём ещё
            await asyncio.sleep(1)
        else:
            # Давно не печатал — можно отвечать
            break

    # Чистим метку typing
    _last_typing.pop(key, None)

    # Шаг 3: собираем буфер
    buffered = _pending_messages.pop(key, [])
    _pending_tasks.pop(key, None)
    if not buffered:
        return

    combined_input = "\n".join(buffered)

    # Шаг 4: контекст
    context_size = int(user.get("context", "10"))
    messages = await _build_context(client, sender_tg_id, context_size, combined_input)

    # Шаг 5: роль
    system_prompt, temp_key = _get_role(user.get("role"))

    # Шаг 6: запрос
    logger.info(f"[{acc_id}] Запрос к OpenRouter для user {sender_id}")
    response = await ask(system_prompt=system_prompt, messages=messages, temperature_key=temp_key)
    if not response:
        logger.warning(f"[{acc_id}] Пустой ответ от OpenRouter")
        return

    # Шаг 7: отправка
    await client.send_message(sender_tg_id, f"{response}\n\n@bot")
    logger.info(f"[{acc_id}] Ответ отправлен → {sender_id}")


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