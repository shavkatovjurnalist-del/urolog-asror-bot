"""Mini App uchun JSON API.

Bot va Mini App aynan bir xil ma'lumotni ko'rsatishi uchun ikkalasi ham
`app.repo` orqali bitta bazadan o'qiydi.
"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import repo, report
from app.ai import answer as ai_answer
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
    preferred_time: str = ""
    comment: str = ""

    model_config = {"populate_by_name": True}


class ConsultationIn(BaseModel):
    init_data: str = Field(default="", alias="initData")
    message: str

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
                tg_user.id,
                f"✅ <b>Arizangiz qabul qilindi!</b> (№{appt.id})\n\n"
                "Shifokor yordamchisi tez orada siz bilan bog'lanadi.",
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
