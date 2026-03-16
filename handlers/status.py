import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from config import load_data, save_data, SESSIONS_DIR
from modules.telethon_manager import is_connected

router = Router()


def _get_account_state(acc_id: str, acc: dict) -> tuple[str, str]:
    """
    Возвращает (icon, state_str) для аккаунта.
    Порядок проверок:
    1. Файл сессии существует?
    2. Клиент подключён в памяти?
    3. Включён/выключен вручную?
    """
    session_file = acc.get("session_file", f"{SESSIONS_DIR}/{acc_id}.session")
    session_exists = os.path.exists(session_file)
    connected = is_connected(acc_id)
    enabled = acc.get("enabled", True)

    if not session_exists:
        return "❌", "❌ Нет файла сессии"
    if not connected:
        return "⚠️", "⚠️ Не подключён"
    if not enabled:
        return "🔴", "🔴 Выключен"
    return "🟢", "🟢 Активен"


def _build_status_keyboard(accounts: dict, bot_enabled: bool) -> object:
    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(
        text=f"🤖 Бот: {'🟢 Включён' if bot_enabled else '🔴 Выключен'} — переключить",
        callback_data="status:toggle_bot"
    ))

    if accounts:
        builder.row(InlineKeyboardButton(
            text="── Аккаунты ──",
            callback_data="noop"
        ))
        for acc_id, acc in accounts.items():
            uname = f"@{acc['username']}" if acc.get("username") else acc_id
            icon, _ = _get_account_state(acc_id, acc)
            builder.row(InlineKeyboardButton(
                text=f"{icon} {uname}",
                callback_data=f"status:toggle_acc:{acc_id}"
            ))

    builder.row(InlineKeyboardButton(text="🔄 Обновить", callback_data="status:refresh"))
    builder.row(InlineKeyboardButton(text="❌ Закрыть",  callback_data="close"))
    return builder.as_markup()


def _build_status_text(accounts: dict, bot_enabled: bool) -> str:
    lines = [
        f"📊 Статус бота: {'🟢 Включён' if bot_enabled else '🔴 Выключен'}",
        f"📱 Аккаунтов: {len(accounts)}",
        ""
    ]
    for acc_id, acc in accounts.items():
        uname = f"@{acc['username']}" if acc.get("username") else acc_id
        users_count = len(acc.get("users", {}))
        _, state_str = _get_account_state(acc_id, acc)
        lines.append(f"{state_str} {uname} · 👥 {users_count}")

    return "\n".join(lines)


# ── Показать статус ───────────────────────────────────────────

@router.message(F.text == "📊 Статус")
async def status_handler(message: Message):
    data = load_data()
    await message.answer(
        _build_status_text(data.get("accounts", {}), data.get("bot_enabled", True)),
        reply_markup=_build_status_keyboard(data.get("accounts", {}), data.get("bot_enabled", True))
    )


@router.callback_query(F.data == "status:refresh")
async def status_refresh(callback: CallbackQuery):
    data = load_data()
    await callback.message.edit_text(
        _build_status_text(data.get("accounts", {}), data.get("bot_enabled", True)),
        reply_markup=_build_status_keyboard(data.get("accounts", {}), data.get("bot_enabled", True))
    )
    await callback.answer("🔄 Обновлено")


# ── Переключить бот ───────────────────────────────────────────

@router.callback_query(F.data == "status:toggle_bot")
async def toggle_bot(callback: CallbackQuery):
    data = load_data()
    data["bot_enabled"] = not data.get("bot_enabled", True)
    save_data(data)
    await callback.message.edit_text(
        _build_status_text(data.get("accounts", {}), data["bot_enabled"]),
        reply_markup=_build_status_keyboard(data.get("accounts", {}), data["bot_enabled"])
    )
    await callback.answer(f"Бот {'включён 🟢' if data['bot_enabled'] else 'выключен 🔴'}")


# ── Переключить аккаунт ───────────────────────────────────────

@router.callback_query(F.data.startswith("status:toggle_acc:"))
async def toggle_account(callback: CallbackQuery):
    acc_id = callback.data.split(":")[2]
    data = load_data()
    acc = data["accounts"].get(acc_id)
    if not acc:
        await callback.answer("❌ Аккаунт не найден", show_alert=True)
        return

    # Нельзя включить если нет файла сессии или клиент не подключён
    session_file = acc.get("session_file", f"{SESSIONS_DIR}/{acc_id}.session")
    if not os.path.exists(session_file):
        await callback.answer("❌ Файл сессии не найден. Переподключите аккаунт.", show_alert=True)
        return
    if not is_connected(acc_id):
        await callback.answer("⚠️ Клиент не подключён. Перезапустите бота.", show_alert=True)
        return

    acc["enabled"] = not acc.get("enabled", True)
    save_data(data)

    uname = f"@{acc['username']}" if acc.get("username") else acc_id
    await callback.message.edit_text(
        _build_status_text(data.get("accounts", {}), data.get("bot_enabled", True)),
        reply_markup=_build_status_keyboard(data.get("accounts", {}), data.get("bot_enabled", True))
    )
    await callback.answer(f"{uname} {'включён 🟢' if acc['enabled'] else 'выключен 🔴'}")
