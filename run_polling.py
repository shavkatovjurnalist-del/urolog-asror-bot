"""Lokal sinov uchun: botni polling rejimida ishga tushirish.

Mini App tugmasi ishlashi uchun BASE_URL https bo'lishi shart (masalan ngrok).
"""
from __future__ import annotations

import asyncio
import logging

from app.bot.instance import bot, dp
from app.db import init_db

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    await init_db()
    from sqlalchemy import func, select

    from app.db import SessionLocal
    from app.models import Service

    async with SessionLocal() as s:
        if not (await s.execute(select(func.count(Service.id)))).scalar():
            from app.seed import seed

            await seed()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
