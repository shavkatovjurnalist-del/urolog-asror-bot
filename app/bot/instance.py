"""Bot va Dispatcher yagona nusxasi."""
from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import live_router, router, support_router
from app.bot.operator import operator_router
from app.config import BOT_TOKEN, REPORT_BOT_TOKEN

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# AI operator boti (@ai_humoyunbot) — boshqaruv kanali. Alohida Dispatcher:
# uning update'lari bemor botining handlerlariga umuman tushmasligi kerak.
op_bot = (
    Bot(token=REPORT_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    if REPORT_BOT_TOKEN
    else None
)
op_dp = Dispatcher(storage=MemoryStorage())
op_dp.include_router(operator_router)
# Tartib muhim.
# 1) Operator guruhi — u yerdagi xabar admin javobi, bemor savoli emas.
# 2) Jonli suhbat — bemor suhbat davomida menyu tugmasining matnini yozib
#    yuborsa ham, xabar AI ga boradi, boshqa bo'limga sakramaydi.
dp.include_router(support_router)
dp.include_router(live_router)
dp.include_router(router)
