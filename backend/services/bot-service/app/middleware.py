from fastapi import Request
from app.bot_loader import bot

async def bot_middleware(request: Request, call_next):
    request.state.bot = bot
    response = await call_next(request)
    return response
    

async def get_bot(request: Request):
    return request.state.bot