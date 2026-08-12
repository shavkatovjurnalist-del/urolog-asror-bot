"""AI operator boti (@ai_humoyunbot) — boshqaruv paneli.

Bu bot bemorlar bilan gaplashmaydi: u shifokor va Bobur uchun xizmat
kanali. Unga signallar, kunlik xulosalar va arizalar tushadi, hamda
undan turib AI ni favqulodda to'xtatib qo'yish mumkin.

**Xavfsizlik.** Botga begona odam yozishi mumkin (username ochiq), lekin
u hech narsa ko'rmaydi va hech narsani boshqara olmaydi: har bir xabar
`ALLOWED` ro'yxatiga solishtiriladi. Ro'yxat `.env` dagi `ADMIN_IDS` va
`REPORT_CHAT_IDS` dan yig'iladi — ya'ni signal keladigan chatlarning
o'zi. Begonaga faqat quruq bir qator qaytadi.

**Favqulodda kodlar:**
    404 — AI shu zahoti to'xtaydi (Telegram ham, Instagram ham);
    101 — AI qaytadi.
To'xtatilgan holatda bemor xabarlari guruhga tushaveradi — javobni odam
yozadi. Bu qasddan: «to'xtatish» degani mijozni yo'qotish degani emas.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import Message

from app import ig_bridge, repo
from app.config import ADMIN_IDS, REPORT_CHAT_IDS

log = logging.getLogger(__name__)

operator_router = Router()

# Kim boshqara oladi. Bo'sh bo'lsa hech kim — bu xavfsiz sukut holati.
ALLOWED: set[int] = {int(x) for x in (*ADMIN_IDS, *REPORT_CHAT_IDS)}

STOP_CODE = "404"
START_CODE = "101"

STRANGER = "Bu bot xizmat uchun. Savolingiz bo'lsa @urolog_astorturayevbot ga yozing."


def _allowed(message: Message) -> bool:
    uid = message.from_user.id if message.from_user else 0
    return uid in ALLOWED or message.chat.id in ALLOWED


@operator_router.message(F.text)
async def operator_message(message: Message) -> None:
    if not _allowed(message):
        # Begonaga tizim haqida hech narsa aytilmaydi.
        log.info("Operator botiga begona murojaat: %s", message.from_user.id)
        await message.answer(STRANGER)
        return

    text = (message.text or "").strip()

    if text == STOP_CODE:
        await repo.set_setting("ai_paused", "true")
        await ig_bridge.set_ai_paused(True)
        await message.answer(
            "⛔️ <b>AI chatbot vaqtinchalik to'xtatildi.</b>\n\n"
            "Telegram va Instagram — ikkalasida ham javob bermaydi.\n"
            "Bemor xabarlari operator guruhiga tushaveradi, javobni "
            "o'zingiz yozasiz.\n\n"
            f"Qayta ishga tushirish: <code>{START_CODE}</code>"
        )
        log.warning("AI TO'XTATILDI (kod 404), kim: %s", message.from_user.id)
        return

    if text == START_CODE:
        await repo.set_setting("ai_paused", "false")
        await ig_bridge.set_ai_paused(False)
        await message.answer(
            "✅ <b>AI chatbot qayta ishga tushdi.</b>\n\n"
            "Endi yangi kelgan xabarlarga suhbat tarixi asosida javob "
            "beradi. To'xtab turgan paytdagi xabarlarga qaytib javob "
            "yozmaydi."
        )
        log.warning("AI QAYTA YOQILDI (kod 101), kim: %s", message.from_user.id)
        return

    if text.lower() in {"/holat", "holat", "/status"}:
        paused = await repo.ai_paused()
        ig = "ulanmagan" if not ig_bridge.enabled() else (
            "to'xtatilgan" if await ig_bridge.is_ai_paused() else "ishlayapti"
        )
        await message.answer(
            f"📊 <b>Holat</b>\n\n"
            f"🤖 AI (Telegram): {'to‘xtatilgan ⛔️' if paused else 'ishlayapti ✅'}\n"
            f"📸 AI (Instagram): {ig}\n\n"
            f"To'xtatish: <code>{STOP_CODE}</code> · "
            f"Yoqish: <code>{START_CODE}</code>"
        )
        return

    await message.answer(
        f"Buyruqlar:\n"
        f"<code>{STOP_CODE}</code> — AI ni to'xtatish\n"
        f"<code>{START_CODE}</code> — AI ni qayta yoqish\n"
        f"<code>holat</code> — hozirgi holat"
    )
