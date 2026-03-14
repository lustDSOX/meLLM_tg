import asyncio
import signal
import sys
from bot import start_bot, dp, bot, stop_bot
from modules.server import app
import uvicorn
from config import BOT_TOKEN

async def run_server():
    config = uvicorn.Config(app, host="0.0.0.0", port=8001, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    if not BOT_TOKEN:
        print("Ошибка: BOT_TOKEN не установлен!")
        sys.exit(1)
    
    try:
        # Параллельный запуск
        await asyncio.gather(
            start_bot(),
            run_server(),
            return_exceptions=True
        )
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        await stop_bot()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Завершение...")
