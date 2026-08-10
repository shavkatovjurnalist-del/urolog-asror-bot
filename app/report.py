"""Hisobotlar — alohida «AI operator» boti (@ai_humoyunbot) orqali yuboriladi.

Faqat `sendMessage` chaqiriladi: o'sha botning webhook'i va boshqa
funksiyalariga umuman tegilmaydi.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from html import escape

import httpx
from sqlalchemy import func, select

from app.config import REPORT_BOT_TOKEN, REPORT_CHAT_IDS
from app.db import SessionLocal
from app.models import Appointment, Clinic, Consultation, Service, User

log = logging.getLogger(__name__)

WEEKDAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun",
          "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]


def fmt_date(dt: datetime) -> str:
    return f"{dt.day}-{MONTHS[dt.month - 1]}, {WEEKDAYS[dt.weekday()]}"


def fmt_time(dt: datetime) -> str:
    return dt.strftime("%H:%M")


async def send(text: str) -> None:
    """Hisobot matnini barcha qabul qiluvchilarga yuboradi."""
    if not REPORT_BOT_TOKEN or not REPORT_CHAT_IDS:
        log.info("Hisobot boti sozlanmagan — yuborilmadi.")
        return

    url = f"https://api.telegram.org/bot{REPORT_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=20) as client:
        for chat_id in REPORT_CHAT_IDS:
            try:
                r = await client.post(url, json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                })
                if not r.json().get("ok"):
                    log.warning("Hisobot yuborilmadi (%s): %s", chat_id, r.text[:200])
            except Exception as e:
                log.warning("Hisobot xatosi (%s): %s", chat_id, e)


# ─────────────────────────── Yangi ariza ───────────────────────────
async def new_appointment(appt: Appointment, clinic: str, service: str, username: str) -> None:
    created = appt.created_at or datetime.utcnow()
    text = (
        f"🆕 <b>YANGI ARIZA</b>  ·  №{appt.id}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>Bemor:</b> {escape(appt.full_name)}\n"
        f"📱 <b>Telefon:</b> <code>{escape(appt.phone)}</code>\n"
        f"🏥 <b>Klinika:</b> {escape(clinic)}\n"
        f"🩺 <b>Masala:</b> {escape(service)}\n"
        f"🕐 <b>Qulay vaqt:</b> {escape(appt.preferred_time or 'ko‘rsatilmagan')}\n"
    )
    if appt.comment:
        text += f"💬 <b>Izoh:</b> {escape(appt.comment)}\n"
    text += (
        f"\n━━━━━━━━━━━━━━━━━━━━\n"
        f"📲 Manba: {'Mini App' if appt.source == 'webapp' else 'Bot menyusi'}\n"
        f"🔗 Telegram: {escape(username or '—')}\n"
        f"🗓 {fmt_date(created)}, {fmt_time(created)}\n\n"
        f"☎️ Bemor bilan bog‘lanish esdan chiqmasin."
    )
    await send(text)


# ─────────────────────────── Yangi murojaat ───────────────────────────
async def new_consultation(c: Consultation, username: str) -> None:
    created = c.created_at or datetime.utcnow()
    text = (
        f"💬 <b>YANGI MUROJAAT</b>  ·  №{c.id}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{escape(c.message)}\n\n"
    )
    if c.ai_answer:
        text += f"🤖 <b>AI javobi:</b>\n{escape(c.ai_answer)}\n\n"
    text += (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📲 Manba: {'Mini App' if c.source == 'webapp' else 'Bot menyusi'}\n"
        f"🔗 Telegram: {escape(username or '—')}\n"
        f"🗓 {fmt_date(created)}, {fmt_time(created)}"
    )
    await send(text)


# ─────────────────────────── Kunlik xulosa ───────────────────────────
async def daily_summary(days: int = 1) -> str:
    """Oxirgi `days` kun bo'yicha xulosa tuzadi va yuboradi."""
    since = datetime.utcnow() - timedelta(days=days)

    async with SessionLocal() as s:
        appts = list((await s.execute(
            select(Appointment).where(Appointment.created_at >= since)
            .order_by(Appointment.created_at)
        )).scalars())
        cons_count = (await s.execute(
            select(func.count(Consultation.id)).where(Consultation.created_at >= since)
        )).scalar() or 0
        new_users = (await s.execute(
            select(func.count(User.id)).where(User.created_at >= since)
        )).scalar() or 0
        total_users = (await s.execute(select(func.count(User.id)))).scalar() or 0

        clinics = {c.id: c.name for c in (await s.execute(select(Clinic))).scalars()}
        services = {x.id: x.title for x in (await s.execute(select(Service))).scalars()}

    now = datetime.utcnow()
    header = (
        f"📊 <b>KUNLIK XULOSA</b>\n"
        f"🗓 {fmt_date(now)}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📅 Yangi arizalar: <b>{len(appts)} ta</b>\n"
        f"💬 Murojaatlar: <b>{cons_count} ta</b>\n"
        f"👥 Yangi foydalanuvchilar: <b>{new_users} ta</b>\n"
        f"👤 Jami foydalanuvchilar: <b>{total_users} ta</b>\n"
    )

    if not appts:
        body = "\n━━━━━━━━━━━━━━━━━━━━\nBugun yangi ariza tushmadi."
    else:
        # Qaysi yo'nalishlar ko'p so'ralgani
        by_service: dict[str, int] = {}
        for a in appts:
            key = services.get(a.service_id, "Umumiy maslahat")
            by_service[key] = by_service.get(key, 0) + 1
        top = sorted(by_service.items(), key=lambda x: -x[1])

        body = "\n━━━━━━━━━━━━━━━━━━━━\n🔥 <b>Ko‘p so‘ralgan yo‘nalishlar</b>\n"
        for title, n in top[:5]:
            body += f"  • {escape(title)} — {n} ta\n"

        body += "\n📋 <b>Arizalar ro‘yxati</b>\n"
        for a in appts:
            body += (
                f"\n<b>№{a.id}</b> · {escape(a.full_name)}\n"
                f"   📱 <code>{escape(a.phone)}</code>\n"
                f"   🩺 {escape(services.get(a.service_id, 'Umumiy maslahat'))}\n"
                f"   🏥 {escape(clinics.get(a.clinic_id, 'Farqi yo‘q'))}\n"
                f"   🕐 {escape(a.preferred_time or 'ko‘rsatilmagan')}"
                f" · holat: {escape(a.status)}\n"
            )

    text = header + body + "\n━━━━━━━━━━━━━━━━━━━━\n🤖 Dr. Asror To‘rayev boti"

    # Telegram cheklovi — 4096 belgi
    for chunk in [text[i:i + 3900] for i in range(0, len(text), 3900)]:
        await send(chunk)
    return text
