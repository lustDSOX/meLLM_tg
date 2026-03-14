import aiohttp
import logging
from config import API_TOKEN, API_MODEL, FREQUENCY_PENALTY, MAX_TOKENS, PRESENCE_PENALTY
from keyboards import TEMPERATURE_LEVELS

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


async def ask(system_prompt: str, messages: list[dict], temperature_key: str = "balanced") -> str | None:
    _, temperature = TEMPERATURE_LEVELS.get(temperature_key, ("", 0.7))
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type":  "application/json"
    }
    payload = {
        "model":    API_MODEL,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "temperature":       temperature,
        "max_tokens":        MAX_TOKENS,
        "frequency_penalty": FREQUENCY_PENALTY,
        "presence_penalty":  PRESENCE_PENALTY,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(OPENROUTER_URL, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"OpenRouter error {resp.status}: {text}")
                    return None
                data = await resp.json()
                return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"OpenRouter request failed: {e}")
        return None
