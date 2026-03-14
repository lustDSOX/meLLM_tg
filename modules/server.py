import time
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from config import BOT_TOKEN

start_time = time.time()
bot_status = "running"

app = FastAPI()

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "uptime": time.time() - start_time,
        "bot_status": bot_status,
        "bot_token_set": bool(BOT_TOKEN)
    }

# Lifecycle hooks
@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_status
    bot_status = "starting"
    yield
    bot_status = "stopping"

app.router.lifespan_context = lifespan
