"""FastAPI ilova: Telegram webhook + Mini App (static) + JSON API."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from aiogram.types import MenuButtonWebApp, Update, WebAppInfo
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.admin import router as admin_router
from app.api import router as api_router
from app.bot.instance import bot, dp
from app.config import BASE_URL, WEBAPP_DIR, WEBAPP_URL, WEBHOOK_PATH
from app.db import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("urolog-bot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    # Kontentni har safar sinxronlaymiz (upsert) — `app/seed.py` ni tahrirlab
    # push qilish kifoya, deploy'dan keyin o'zgarish avtomatik qo'llanadi.
    from app.seed import seed

    try:
        await seed()
    except Exception as e:  # kontent xatosi botni to'xtatmasin
        log.exception("Kontent yuklashda xato: %s", e)

    if BASE_URL.startswith("https://"):
        await bot.set_webhook(
            url=f"{BASE_URL}{WEBHOOK_PATH}",
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query", "my_chat_member"],
        )
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Sayt", web_app=WebAppInfo(url=WEBAPP_URL))
        )
        log.info("Webhook o'rnatildi: %s%s", BASE_URL, WEBHOOK_PATH)
    else:
        log.warning("BASE_URL https emas — webhook o'rnatilmadi (lokal rejim).")

    # Kunlik xulosa jadvali (Toshkent vaqti bilan 20:00)
    import asyncio

    from app.report import daily_scheduler

    task = asyncio.create_task(daily_scheduler())

    yield

    task.cancel()
    await bot.session.close()


app = FastAPI(title="Dr. Asror To'rayev — Bot & Mini App", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)
app.include_router(admin_router)


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request) -> Response:
    data = await request.json()
    await dp.feed_update(bot, Update.model_validate(data, context={"bot": bot}))
    return Response(status_code=200)


@app.get("/health")
async def health() -> dict:
    return {"ok": True}


@app.get("/")
async def root() -> dict:
    return {"service": "urolog-asror-bot", "webapp": WEBAPP_URL}


app.mount("/app", StaticFiles(directory=WEBAPP_DIR, html=True), name="webapp")
