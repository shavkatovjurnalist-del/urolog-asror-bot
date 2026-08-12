"""FastAPI ilova: Telegram webhook + Mini App (static) + JSON API."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from aiogram.types import MenuButtonCommands, Update
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.admin import router as admin_router
from app.api import router as api_router
from app.bot.instance import bot, dp, op_bot, op_dp
from app.config import (
    BASE_URL,
    REPORT_WEBHOOK_PATH,
    WEBAPP_DIR,
    WEBAPP_URL,
    WEBHOOK_PATH,
)
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
        # Mini App'ga kirish faqat klaviaturadagi «🌐 Sayt (Mini App)» tugmasi orqali.
        # Yuqoridagi menyu tugmasi ikkilanish bo'lmasligi uchun standart holatga qaytarilgan.
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        log.info("Webhook o'rnatildi: %s%s", BASE_URL, WEBHOOK_PATH)

        # AI operator botining webhook'i. Ilgari u n8n'ga ulangan edi, lekin
        # u yerda Telegram kanali o'chirilgan va hech narsa qilmasdi.
        if op_bot is not None:
            try:
                await op_bot.set_webhook(
                    url=f"{BASE_URL}{REPORT_WEBHOOK_PATH}",
                    drop_pending_updates=True,
                    allowed_updates=["message"],
                )
                log.info("Operator boti webhook'i o'rnatildi.")
            except Exception as e:
                log.warning("Operator boti webhook'i o'rnatilmadi: %s", e)
    else:
        log.warning("BASE_URL https emas — webhook o'rnatilmadi (lokal rejim).")

    # Fon vazifalari: kunlik xulosalar va javob kutish nazorati
    import asyncio

    from app import ig_bridge
    from app.report import daily_scheduler
    from app.support import pending_watcher

    tasks = [
        asyncio.create_task(daily_scheduler()),
        asyncio.create_task(pending_watcher(bot)),
    ]
    if ig_bridge.enabled():
        # Instagram signallari ham shu servis orqali yuboriladi — xabar
        # ko'rinishi va tugmalari ikkala kanalda bir xil bo'lsin.
        tasks.append(asyncio.create_task(ig_bridge.escalation_watcher()))
        log.info("Instagram ko'prigi yoqildi.")

    yield

    for task in tasks:
        task.cancel()
    await ig_bridge.close()
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


@app.post(REPORT_WEBHOOK_PATH)
async def operator_webhook(request: Request) -> Response:
    """AI operator boti (@ai_humoyunbot) — favqulodda kodlar shu yerga tushadi."""
    if op_bot is None:
        return Response(status_code=200)
    data = await request.json()
    await op_dp.feed_update(op_bot, Update.model_validate(data, context={"bot": op_bot}))
    return Response(status_code=200)


@app.get("/health")
async def health() -> dict:
    return {"ok": True}


@app.get("/")
async def root() -> dict:
    return {"service": "urolog-asror-bot", "webapp": WEBAPP_URL}


app.mount("/app", StaticFiles(directory=WEBAPP_DIR, html=True), name="webapp")
