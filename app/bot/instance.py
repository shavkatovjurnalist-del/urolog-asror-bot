"""Bot va Dispatcher yagona nusxasi."""
from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import live_router, router
from app.config import BOT_TOKEN

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
# Tartib muhim: jonli suhbat birinchi. Bemor suhbat davomida menyu tugmasining
# matnini yozib yuborsa ham, xabar AI ga boradi, boshqa bo'limga sakramaydi.
dp.include_router(live_router)
dp.include_router(router)
