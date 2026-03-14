from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from config import load_data, save_data
from modules.telethon_manager import is_connected

router = Router()


def _build_status_keyboard(accounts: dict, bot_enabled: bool) -> object:
    builder = InlineKeyboardBuilder()

    # Глобальный переключатель бота
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
            connected = is_connected(acc_id)
            enabled = acc.get("enabled", True)

            if not connected:
                icon = "⚠️"   # сессия есть, но не подключён
            elif enabled:
                icon = "🟢"
            else:
                icon = "🔴"

            builder.row(InlineKeyboardButton(
                text=f"{icon} {uname}",
                callback_data=f"status:toggle_acc:{acc_id}"
            ))

    builder.row(InlineKeyboardButton(
        text="🔄 Обновить",
        callback_data="status:refresh"
    ))
    builder.row(InlineKeyboardButton(
        text="❌ Закрыть",
        callback_data="close"
    ))
    return builder.as_markup()


def _build_status_text(accounts: dict, bot_enabled: bool) -> str:
    lines = [
        f"📊 Статус бота: {'🟢 Включён' if bot_enabled else '🔴 Выключен'}",
        f"📱 Аккаунтов: {len(accounts)}",
        ""
    ]
    for acc_id, acc in accounts.items():
        uname = f"@{acc['username']}" if acc.get("username") else acc_id
        connected = is_connected(acc_id)
        enabled = acc.get("enabled", True)
        users_count = len(acc.get("users", {}))

        if not connected:
            state_str = "⚠️ Нет сессии"
        elif enabled:
            state_str = "🟢 Активен"
        else:
            state_str = "🔴 Выключен"

        lines.append(f"{state_str} {uname} · 👥 {users_count}")

    return "\n".join(lines)


# ── Показать статус ───────────────────────────────────────────

@router.message(F.text == "📊 Статус")
async def status_handler(message: Message):
    data = load_data()
    accounts = data.get("accounts", {})
    bot_enabled = data.get("bot_enabled", True)
    await message.answer(
        _build_status_text(accounts, bot_enabled),
        reply_markup=_build_status_keyboard(accounts, bot_enabled)
    )


@router.callback_query(F.data == "status:refresh")
async def status_refresh(callback: CallbackQuery):
    data = load_data()
    accounts = data.get("accounts", {})
    bot_enabled = data.get("bot_enabled", True)
    await callback.message.edit_text(
        _build_status_text(accounts, bot_enabled),
        reply_markup=_build_status_keyboard(accounts, bot_enabled)
    )
    await callback.answer("🔄 Обновлено")


# ── Переключить глобальный бот ────────────────────────────────

@router.callback_query(F.data == "status:toggle_bot")
async def toggle_bot(callback: CallbackQuery):
    data = load_data()
    data["bot_enabled"] = not data.get("bot_enabled", True)
    save_data(data)
    accounts = data.get("accounts", {})
    await callback.message.edit_text(
        _build_status_text(accounts, data["bot_enabled"]),
        reply_markup=_build_status_keyboard(accounts, data["bot_enabled"])
    )
    state_str = "включён 🟢" if data["bot_enabled"] else "выключен 🔴"
    await callback.answer(f"Бот {state_str}")


# ── Переключить конкретный аккаунт ────────────────────────────

@router.callback_query(F.data.startswith("status:toggle_acc:"))
async def toggle_account(callback: CallbackQuery):
    acc_id = callback.data.split(":")[2]
    data = load_data()
    acc = data["accounts"].get(acc_id)
    if not acc:
        await callback.answer("❌ Аккаунт не найден", show_alert=True)
        return

    acc["enabled"] = not acc.get("enabled", True)
    save_data(data)

    uname = f"@{acc['username']}" if acc.get("username") else acc_id
    state_str = "включён 🟢" if acc["enabled"] else "выключен 🔴"

    accounts = data.get("accounts", {})
    bot_enabled = data.get("bot_enabled", True)
    await callback.message.edit_text(
        _build_status_text(accounts, bot_enabled),
        reply_markup=_build_status_keyboard(accounts, bot_enabled)
    )
    await callback.answer(f"{uname} {state_str}")
