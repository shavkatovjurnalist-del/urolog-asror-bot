"""Mini App uchun JSON API.

Bot va Mini App aynan bir xil ma'lumotni ko'rsatishi uchun ikkalasi ham
`app.repo` orqali bitta bazadan o'qiydi.
"""
from __future__ import annotations

import logging
from datetime import datetime
from html import escape

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import ai, persona, repo, report
from app.ai import answer as ai_answer
from app.bot import calendar as cal
from app.bot import texts as t
from app.config import ASK_ENABLED
from app.db import get_session
from app.webapp_auth import InitDataError, TgUser, parse_init_data

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# ─────────────────────────── Kontent ───────────────────────────
@router.get("/content")
async def content(s: AsyncSession = Depends(get_session)) -> dict:
    doctor = await repo.get_doctor(s)
    services = await repo.get_services(s)
    methods = await repo.get_methods(s)
    advantages = await repo.get_advantages(s)
    clinics = await repo.get_clinics(s)
    results = await repo.get_results(s)
    faq = await repo.get_faq(s)

    return {
        "flags": {"ask_enabled": ASK_ENABLED},
        "schedule": {
            "slots": cal.TIME_SLOTS,
            "min_date": cal.min_date().isoformat(),
            "max_date": cal.max_date().isoformat(),
            "closed_weekdays": sorted(cal.WEEKEND),  # 5=shanba, 6=yakshanba
            "lunch": "13:00 – 14:00",
        },
        "doctor": {
            "full_name": doctor.full_name,
            "short_name": doctor.short_name,
            "specialty": doctor.specialty,
            "category": doctor.category,
            "experience": doctor.experience,
            "bio": doctor.bio,
            "photo": doctor.photo,
            "phone": doctor.phone,
            "email": doctor.email,
            "telegram": doctor.telegram,
            "instagram": doctor.instagram,
            "youtube": doctor.youtube,
            "website": doctor.website,
            "work_hours": doctor.work_hours,
        },
        "services": [
            {
                "id": x.id, "icon": x.icon, "title": x.title,
                "short": x.short, "description": x.description,
            }
            for x in services
        ],
        "methods": [
            {"id": x.id, "icon": x.icon, "title": x.title, "description": x.description}
            for x in methods
        ],
        "advantages": [
            {"icon": x.icon, "title": x.title, "description": x.description} for x in advantages
        ],
        "clinics": [
            {
                "id": x.id, "name": x.name, "address": x.address, "landmark": x.landmark,
                "map_url": x.map_url, "photo": x.photo, "work_hours": x.work_hours,
                "lat": x.latitude, "lng": x.longitude,
            }
            for x in clinics
        ],
        "results": [
            {"id": x.id, "title": x.title, "youtube_id": x.youtube_id,
             "url": x.url, "thumb": x.thumb}
            for x in results
        ],
        "faq": [{"q": x.question, "a": x.answer} for x in faq],
    }


# ─────────────────────────── So'rov modellari ───────────────────────────
class AppointmentIn(BaseModel):
    init_data: str = Field(default="", alias="initData")
    full_name: str
    phone: str
    clinic_id: int | None = None
    service_id: int | None = None
    scheduled_at: str = ""
    preferred_time: str = ""
    comment: str = ""

    model_config = {"populate_by_name": True}


class ConsultationIn(BaseModel):
    init_data: str = Field(default="", alias="initData")
    message: str

    model_config = {"populate_by_name": True}


class ChatIn(BaseModel):
    init_data: str = Field(default="", alias="initData")
    message: str = ""

    model_config = {"populate_by_name": True}


def _tg_user(init_data: str):
    if not init_data:
        return None
    try:
        data = parse_init_data(init_data)
    except InitDataError as e:
        raise HTTPException(status_code=401, detail=f"initData xato: {e}") from e
    return TgUser(data["user"]) if data.get("user") else None


# ─────────────────────────── Qabulga yozilish ───────────────────────────
@router.post("/appointments")
async def create_appointment(
    payload: AppointmentIn, s: AsyncSession = Depends(get_session)
) -> dict:
    if len(payload.full_name.strip()) < 3:
        raise HTTPException(400, "Ism to'liq emas")
    digits = "".join(c for c in payload.phone if c.isdigit())
    if len(digits) < 9:
        raise HTTPException(400, "Telefon raqami noto'g'ri")

    # Sana va vaqt: ertangi kundan boshlab, dam olish kunlarisiz, ish soatlarida
    scheduled = None
    if payload.scheduled_at:
        try:
            scheduled = datetime.fromisoformat(payload.scheduled_at)
        except ValueError:
            raise HTTPException(400, "Sana formati noto'g'ri") from None
        if scheduled.date() < cal.min_date():
            raise HTTPException(400, "Faqat ertangi kundan boshlab yozilish mumkin")
        if scheduled.date() > cal.max_date():
            raise HTTPException(400, "Sana juda uzoq")
        if scheduled.weekday() in cal.WEEKEND:
            raise HTTPException(400, "Shanba va yakshanba qabul yo'q")
        if scheduled.strftime("%H:%M") not in cal.TIME_SLOTS:
            raise HTTPException(400, "Bu soatda qabul yo'q")

    tg_user = _tg_user(payload.init_data)
    user = await repo.upsert_user(s, tg_user, source="webapp") if tg_user else None

    appt = await repo.create_appointment(
        s,
        user_id=user.id if user else None,
        tg_id=tg_user.id if tg_user else None,
        full_name=payload.full_name.strip(),
        phone=payload.phone.strip(),
        clinic_id=payload.clinic_id or None,
        service_id=payload.service_id or None,
        scheduled_at=scheduled,
        preferred_time=payload.preferred_time.strip(),
        comment=payload.comment.strip(),
        source="webapp",
    )

    clinic = await repo.get_clinic(s, appt.clinic_id) if appt.clinic_id else None
    service = await repo.get_service(s, appt.service_id) if appt.service_id else None

    clinic_name = clinic.name if clinic else "Farqi yo'q"
    service_name = service.title if service else "Umumiy maslahat"
    username = f"@{tg_user.username}" if tg_user and tg_user.username else "Mini App"

    from app.bot.handlers import notify_admins
    from app.bot.instance import bot

    await notify_admins(bot, t.admin_appointment(appt, clinic_name, service_name, username))
    await report.new_appointment(appt, clinic_name, service_name, username)

    if tg_user:
        try:
            await bot.send_message(
                tg_user.id, t.appointment_accepted(appt.id, appt.preferred_time)
            )
        except Exception as e:
            log.warning("Bemorga xabar yuborilmadi: %s", e)

    return {"ok": True, "id": appt.id}


# ─────────────────────────── Murojaat (AI joyi) ───────────────────────────
@router.post("/consultations")
async def create_consultation(
    payload: ConsultationIn, s: AsyncSession = Depends(get_session)
) -> dict:
    if not ASK_ENABLED:
        raise HTTPException(503, "Murojaat bo'limi hozircha yopiq — AI-konsultant tayyorlanmoqda")

    msg = payload.message.strip()
    if len(msg) < 5:
        raise HTTPException(400, "Savol juda qisqa")

    tg_user = _tg_user(payload.init_data)
    user = await repo.upsert_user(s, tg_user, source="webapp") if tg_user else None

    c = await repo.create_consultation(
        s,
        user_id=user.id if user else None,
        tg_id=tg_user.id if tg_user else None,
        message=msg,
        source="webapp",
    )

    # AI ulanganda javob shu yerdan qaytadi.
    reply = await ai_answer(msg)
    if reply:
        c.ai_answer = reply
        c.answered_by = "ai"
        c.answered_at = datetime.utcnow()
        c.status = "answered"
        await s.commit()

    username = f"@{tg_user.username}" if tg_user and tg_user.username else "Mini App"

    from app.bot.handlers import notify_admins
    from app.bot.instance import bot

    await notify_admins(bot, t.admin_consultation(c, username))
    await report.new_consultation(c, username)

    return {"ok": True, "id": c.id, "answer": reply}


# ─────────────────────────── Jonli murojaat (AI suhbati) ───────────────────────────
# Bot va Mini App bitta suhbatni yuritadi — kalit `tg_id`. Bemor Mini App'da
# boshlab, botda davom ettirsa ham AI oldingi gaplarni eslaydi.
def _require_chat_user(init_data: str):
    if not ASK_ENABLED:
        raise HTTPException(503, "Jonli murojaat hozircha yopiq")
    tg_user = _tg_user(init_data)
    if not tg_user:
        raise HTTPException(401, "Suhbat uchun Mini App'ni Telegram orqali oching")
    return tg_user


@router.post("/chat/start")
async def chat_start(payload: ChatIn, s: AsyncSession = Depends(get_session)) -> dict:
    tg_user = _require_chat_user(payload.init_data)
    await repo.upsert_user(s, tg_user, source="webapp")
    await repo.clear_chat_history(s, tg_user.id)
    await repo.add_chat_message(
        s, tg_user.id, "model", persona.GREETING, source="webapp"
    )
    return {"ok": True, "greeting": persona.GREETING}


@router.post("/chat")
async def chat_send(payload: ChatIn, s: AsyncSession = Depends(get_session)) -> dict:
    tg_user = _require_chat_user(payload.init_data)
    text = payload.message.strip()
    if not text:
        raise HTTPException(400, "Xabar bo'sh")

    from app.bot.handlers import notify_admins
    from app.bot.instance import bot

    username = f"@{tg_user.username}" if tg_user.username else "Mini App"

    # Shoshilinch holat — modelga bormaydi.
    if ai.is_urgent(text):
        await repo.add_chat_message(
            s, tg_user.id, "user", text, source="webapp", flags="shoshilinch"
        )
        await repo.add_chat_message(
            s, tg_user.id, "model", persona.URGENT, source="webapp", flags="shoshilinch"
        )
        alert = (
            f"🔔 <b>Jonli suhbat — 🚨 SHOSHILINCH</b> (Mini App)\n\n"
            f"👤 {escape(username)} · <code>{tg_user.id}</code>\n💬 {escape(text[:600])}"
        )
        await notify_admins(bot, alert)
        await report.send(alert)
        return {"ok": True, "reply": persona.URGENT, "flags": ["shoshilinch"]}

    history = await repo.get_chat_history(s, tg_user.id, limit=ai.HISTORY_LIMIT)
    await repo.add_chat_message(s, tg_user.id, "user", text, source="webapp")

    reply, flags = await ai.chat(text, history=history)
    if not reply:
        log.warning("AI javob bermadi (webapp %s): %s", tg_user.id, ",".join(flags))
        reply, flags = persona.FALLBACK, flags + ["fallback"]

    await repo.add_chat_message(
        s, tg_user.id, "model", reply, source="webapp", flags=",".join(flags)
    )

    # Suhbatni shifokorga bir marta bildirish — birinchi savol bo'yicha.
    prior = [m for m in history if m["role"] == "user"]
    if not prior:
        user = await repo.upsert_user(s, tg_user, source="webapp")
        c = await repo.create_consultation(
            s, user_id=user.id, tg_id=tg_user.id, message=text, source="webapp-live"
        )
        await report.new_consultation(c, username)

    price_asked = ai.asks_price(text) or "narx" in flags
    if price_asked or "fallback" in flags:
        reason = "Narx so'raldi" if price_asked else "⚠️ AI javob berolmadi"
        alert = (
            f"🔔 <b>Jonli suhbat — {reason}</b> (Mini App)\n\n"
            f"👤 {escape(username)} · <code>{tg_user.id}</code>\n💬 {escape(text[:600])}"
        )
        await notify_admins(bot, alert)
        await report.send(alert)

    return {"ok": True, "reply": reply, "flags": flags}


@router.post("/chat/end")
async def chat_end(payload: ChatIn, s: AsyncSession = Depends(get_session)) -> dict:
    tg_user = _require_chat_user(payload.init_data)
    history = await repo.get_chat_history(s, tg_user.id, limit=60)
    await repo.clear_chat_history(s, tg_user.id)
    if any(m["role"] == "user" for m in history):
        username = f"@{tg_user.username}" if tg_user.username else "Mini App"
        await report.live_chat_transcript(history, username, tg_user.id)
    return {"ok": True}


# ─────────────────────────── Kunlik xulosa ───────────────────────────
@router.get("/report/daily")
async def daily_report(key: str = "") -> dict:
    """Kunlik xulosani hisobot botiga yuboradi.

    cron-job.org kabi xizmatdan har kuni chaqiriladi:
    https://<servis>.onrender.com/api/report/daily?key=<WEBHOOK_SECRET>
    """
    from app.config import WEBHOOK_SECRET

    if key != WEBHOOK_SECRET:
        raise HTTPException(403, "Kalit noto'g'ri")
    text = await report.daily_summary()
    return {"ok": True, "length": len(text)}
