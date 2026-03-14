import asyncio
import os
import logging
import uuid
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery
from telethon import TelegramClient
from telethon.errors import (
    PhoneNumberInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
    PasswordHashInvalidError
)

from config import (
    TG_API, TG_HASH,
    SESSIONS_DIR,
    get_accounts, get_account,
    create_account, delete_account
)
from keyboards import accounts_menu, account_detail

router = Router()
logger = logging.getLogger(__name__)

os.makedirs(SESSIONS_DIR, exist_ok=True)


# ── FSM ──────────────────────────────────────────────────────

class AddAccountFSM(StatesGroup):
    waiting_phone   = State()   # ввод номера телефона
    waiting_code    = State()   # ввод кода из SMS
    waiting_password = State()  # ввод 2FA‑пароля


# ── Вспомогательная: полная очистка сессии ───────────────────

async def cleanup_session(client: TelegramClient, session_file: str):
    """Разлогиниться + удалить файл сессии."""
    try:
        if client.is_connected():
            await client.log_out()
    except Exception as e:
        logger.warning(f"Ошибка при logout: {e}")
    finally:
        await client.disconnect()
        if session_file and os.path.exists(session_file):
            os.remove(session_file)
            logger.info(f"Сессия удалена: {session_file}")


# ── Показать список аккаунтов ─────────────────────────────────

@router.message(F.text == "👤 Аккаунты")
async def accounts_handler(message: Message):
    accounts = list(get_accounts().values())
    count = len(accounts)
    text = f"📱 Подключённые аккаунты ({count}):" if count else "📭 Нет подключённых аккаунтов."
    await message.answer(text, reply_markup=accounts_menu(accounts))


@router.callback_query(F.data == "nav:accounts")
async def nav_accounts(callback: CallbackQuery):
    accounts = list(get_accounts().values())
    count = len(accounts)
    text = f"📱 Подключённые аккаунты ({count}):" if count else "📭 Нет подключённых аккаунтов."
    await callback.message.edit_text(text, reply_markup=accounts_menu(accounts))
    await callback.answer()


@router.callback_query(F.data.startswith("acc:open:"))
async def account_open(callback: CallbackQuery):
    acc_id = callback.data.split(":")[2]
    acc = get_account(acc_id)
    if not acc:
        await callback.answer("❌ Аккаунт не найден", show_alert=True)
        return

    uname = f"@{acc['username']}" if acc.get("username") else acc_id
    users = list(acc.get("users", {}).values())
    await callback.message.edit_text(
        f"📱 {uname}\n"
        f"👤 Статус : {'✅ ' if acc.get('enabled', False) else '❌ '}"
        f"👥 Пользователей: {len(users)}",
        reply_markup=account_detail(acc, users)
    )
    await callback.answer()


# ── Добавить аккаунт: запрос номера ───────────────────────────

@router.callback_query(F.data == "acc:add")
async def account_add_start(callback: CallbackQuery, state: FSMContext):
    acc_id = str(uuid.uuid4())[:8] 
    session_file = f"{SESSIONS_DIR}/{acc_id}.session"
    client = TelegramClient(session_file, int(TG_API), TG_HASH)
    await client.connect()

    await state.set_state(AddAccountFSM.waiting_phone)
    await state.update_data(
        acc_id=acc_id,
        session_file=session_file,
        client=client
    )
    await callback.message.answer(
        "📱 Введите номер телефона в международном формате:\n"
        "Пример: +79991234567\n\n"
        "Для отмены введите /cancel"
    )
    await callback.message.delete()
    await callback.answer()


# ── Ввод номера ───────────────────────────────────────────────

@router.message(AddAccountFSM.waiting_phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.startswith("+") or not phone[1:].isdigit():
        await message.answer(
            "❌ Неверный формат. Введите номер вроде +79991234567\n"
            "Или /cancel для отмены."
        )
        return

    data = await state.get_data()
    client: TelegramClient = data["client"]
    session_file = data["session_file"]

    try:
        result = await client.send_code_request(phone)
        await state.update_data(phone=phone, phone_code_hash=result.phone_code_hash)
        await state.set_state(AddAccountFSM.waiting_code)
        await message.answer(
            "🔐 Код отправлен в Telegram. Введите его сюда с пробелами:\n"
            "например 1 2 3 4 5.\n"
            "Или /cancel для отмены."
        )
    except PhoneNumberInvalidError:
        await message.answer("❌ Неверный номер. Проверьте формат и повторите ввод.")
    except Exception as e:
        logger.error(f"send_code_request error: {e}")
        await cleanup_session(client, session_file)
        await state.clear()
        await message.answer(f"❌ Ошибка: {e}")


# ── Ввод кода ─────────────────────────────────────────────────

@router.message(AddAccountFSM.waiting_code)
async def process_code(message: Message, state: FSMContext):
    code = message.text.strip().replace(" ", "")
    if not code.isdigit():
        await message.answer("❌ Код должен состоять только из цифр. Попробуйте ещё раз.")
        return

    data = await state.get_data()
    client: TelegramClient = data["client"]
    phone = data["phone"]
    phone_code_hash = data["phone_code_hash"]
    session_file = data["session_file"]

    try:
        await client.sign_in(
            phone=phone,
            code=code,
            phone_code_hash=phone_code_hash
        )
        # Успех без 2FA
        me = await client.get_me()
        username = me.username or str(me.id)
        create_account(me.id, username)
        await client.disconnect()
        await state.clear()
        accounts = list(get_accounts().values())
        await message.answer(
            f"✅ Аккаунт @{username} подключён!",
            reply_markup=accounts_menu(accounts)
        )
    except SessionPasswordNeededError:
        # Требуется 2FA
        await state.set_state(AddAccountFSM.waiting_password)
        await message.answer(
            "🔐 Аккаунт защищён двухфакторной аутентификацией.\n"
            "Введите пароль 2FA:"
        )
    except PhoneCodeInvalidError:
        await message.answer("❌ Неверный код. Попробуйте ещё раз.")
    except PhoneCodeExpiredError:
        # Код истёк — запрашиваем новый автоматически
        try:
            new_result = await client.send_code_request(phone)
            await state.update_data(phone_code_hash=new_result.phone_code_hash)
            await message.answer(
                "⏰ Предыдущий код истёк. Отправлен новый код.\n"
                "Введите его сюда:\n"
                "Или /cancel для отмены."
            )
            # Остаёмся в состоянии waiting_code
        except Exception as e:
            logger.error(f"Ошибка при повторной отправке кода: {e}")
            await cleanup_session(client, session_file)
            await state.clear()
            await message.answer(f"❌ Не удалось отправить новый код: {e}")
    except Exception as e:
        logger.error(f"sign_in error: {e}")
        await cleanup_session(client, session_file)
        await state.clear()
        await message.answer(f"❌ Ошибка авторизации: {e}")

# ── Ввод 2FA‑пароля ───────────────────────────────────────────

@router.message(AddAccountFSM.waiting_password)
async def process_password(message: Message, state: FSMContext):
    password = message.text.strip()
    data = await state.get_data()
    client: TelegramClient = data["client"]
    session_file = data["session_file"]

    try:
        await client.sign_in(password=password)
        me = await client.get_me()
        username = me.username or str(me.id)
        create_account(me.id, username)
        await client.disconnect()
        await state.clear()
        accounts = list(get_accounts().values())
        await message.answer(
            f"✅ Аккаунт @{username} подключён с 2FA!",
            reply_markup=accounts_menu(accounts)
        )
    except PasswordHashInvalidError:
        await message.answer("❌ Неверный пароль 2FA. Попробуйте ещё раз.")
    except Exception as e:
        logger.error(f"2FA sign_in error: {e}")
        await cleanup_session(client, session_file)
        await state.clear()
        await message.answer(f"❌ Ошибка: {e}")


# ── Отмена авторизации ────────────────────────────────────────

@router.message(
    F.text == "/cancel",
    StateFilter(
        AddAccountFSM.waiting_phone,
        AddAccountFSM.waiting_code,
        AddAccountFSM.waiting_password
    )
)
async def account_add_cancel(message: Message, state: FSMContext):
    data = await state.get_data()
    client: TelegramClient = data.get("client")
    session_file = data.get("session_file")
    if client:
        await cleanup_session(client, session_file)
    await state.clear()
    accounts = list(get_accounts().values())
    await message.answer(
        "❌ Авторизация отменена. Сессия удалена.",
        reply_markup=accounts_menu(accounts)
    )
