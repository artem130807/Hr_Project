from aiogram import Bot, Dispatcher

from app.handlers.general import router as general_router
from app.handlers.candidate.candidate_menu import router as candidate_router
from app.handlers.admin.menu import router as admin_menu_router
from app.handlers.candidate.menu import router as candidate_menu_router
from app.handlers.admin.negotiation import router as negotiation_router

from app.config import BOT_TOKEN


bot = Bot(BOT_TOKEN)
dp = Dispatcher()
dp.include_routers(
    admin_menu_router,
    candidate_menu_router,
    candidate_router,
    negotiation_router,
    general_router
)
