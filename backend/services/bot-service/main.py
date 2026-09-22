import asyncio
import logging

import httpx
import uvicorn
from fastapi import FastAPI, Depends
from aiogram import Bot, Dispatcher
from jwt import PyJWK

from app.endpoints.v1.messages import router as messages_router

from app.utils.auth import verify_external_access, set_public_key
from app.bot_loader import bot, dp
from app.middleware import bot_middleware
from app.config import JWKS_URL

app = FastAPI()
app.middleware("http")(bot_middleware)

app.include_router(messages_router, prefix="/v1", tags=["Messages"], dependencies=[Depends(verify_external_access)])


async def run_bot(bot: Bot, dp: Dispatcher):
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


@app.on_event("startup")
async def on_startup():
    for attempt in range(10):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(JWKS_URL, timeout=5.0)
                resp.raise_for_status()
                jwks = resp.json()
            set_public_key(PyJWK(jwks["keys"][0]).key)
            break
        except Exception:
            if attempt == 9:
                raise
            await asyncio.sleep(3 * (attempt + 1))
    asyncio.create_task(run_bot(bot, dp))

if __name__=="__main__":
    uvicorn.run("main:app",
                host="0.0.0.0",
                port=8002
                )
