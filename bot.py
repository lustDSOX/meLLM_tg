from asyncio.log import logger
import logging
from typing import Any, Callable
from aiogram import F, BaseMiddleware, Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from config import BOT_TOKEN, ADMIN_ID
from handlers import accounts, roles, status, users
from keyboards import main_menu
from modules.telethon_manager import connect_all_accounts, disconnect_all_accounts

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)

class AdminMiddleware(BaseMiddleware):
    """Middleware для роутеров: проверка админа перед хендлерами."""
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Any], Any],
        event: Message | CallbackQuery,
        data: dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        if user_id != ADMIN_ID:
            logger.warning(f"Доступ запрещен для {user_id}")
            if isinstance(event, Message):
                await event.answer("❌ Доступ запрещен. Только для админов.")
            else:
                await event.message.edit_text("❌ Доступ запрещен. Только для админов.")
            return
        return await handler(event, data)

def admin_only():
    """Декоратор-функция для middleware."""
    return AdminMiddleware()

dp = Dispatcher()
dp.message.middleware(admin_only())
dp.callback_query.outer_middleware(admin_only())

dp.include_router(accounts.router)
dp.include_router(status.router)
dp.include_router(roles.router)
dp.include_router(users.router)

@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer(
        "👋 Привет! Выберите раздел:",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "close")
async def close_message(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()

async def start_bot():
    await connect_all_accounts()
    await dp.start_polling(bot)

async def stop_bot():
    await disconnect_all_accounts()
    await bot.session.close()

