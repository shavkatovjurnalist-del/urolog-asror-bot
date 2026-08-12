"""Hisobotlar — alohida «AI operator» boti (@ai_humoyunbot) orqali yuboriladi.

Faqat `sendMessage` chaqiriladi: o'sha botning webhook'i va boshqa
funksiyalariga umuman tegilmaydi.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from html import escape

import httpx
from sqlalchemy import func, select

from app.config import REPORT_BOT_TOKEN, REPORT_CHAT_IDS
from app.db import SessionLocal
from app.models import Appointment, ChatMessage, Clinic, Consultation, Service, User

log = logging.getLogger(__name__)

WEEKDAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun",
          "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]


def fmt_date(dt: datetime) -> str:
    return f"{dt.day}-{MONTHS[dt.month - 1]}, {WEEKDAYS[dt.weekday()]}"


def fmt_time(dt: datetime) -> str:
    return dt.strftime("%H:%M")


async def send(text: str, markup: dict | None = None, fallback: dict | None = None) -> None:
    """Hisobot matnini barcha qabul qiluvchilarga yuboradi.

    `markup` — inline tugmalar. Telegram uni rad etsa (masalan Web App tugmasi
    qo'llab-quvvatlanmasa) `fallback` bilan qayta uriniladi.
    """
    if not REPORT_BOT_TOKEN or not REPORT_CHAT_IDS:
        log.info("Hisobot boti sozlanmagan — yuborilmadi.")
        return

    url = f"https://api.telegram.org/bot{REPORT_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=20) as client:
        for chat_id in REPORT_CHAT_IDS:
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
            if markup:
                payload["reply_markup"] = markup
            try:
                r = await client.post(url, json=payload)
                if r.json().get("ok"):
                    continue
                log.warning("Hisobot yuborilmadi (%s): %s", chat_id, r.text[:200])
                if fallback:
                    payload["reply_markup"] = fallback
                    r2 = await client.post(url, json=payload)
                    if not r2.json().get("ok"):
                        payload.pop("reply_markup", None)
                        await client.post(url, json=payload)
            except Exception as e:
                log.warning("Hisobot xatosi (%s): %s", chat_id, e)


def _action_markups(appt_id: int) -> tuple[dict, dict]:
    """Tasdiqlash/bekor tugmalari: Web App varianti va oddiy havola varianti."""
    from app.admin import make_token
    from app.config import BASE_URL

    ok_url = f"{BASE_URL}/admin/appt?id={appt_id}&action=confirm&token={make_token(appt_id, 'confirm')}"
    no_url = f"{BASE_URL}/admin/appt?id={appt_id}&action=cancel&token={make_token(appt_id, 'cancel')}"

    web_app = {"inline_keyboard": [[
        {"text": "✅ Tasdiqlash", "web_app": {"url": ok_url}},
        {"text": "❌ Bekor qilish", "web_app": {"url": no_url}},
    ]]}
    plain = {"inline_keyboard": [[
        {"text": "✅ Tasdiqlash", "url": ok_url},
        {"text": "❌ Bekor qilish", "url": no_url},
    ]]}
    return web_app, plain


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
        f"🕐 <b>Qabul vaqti:</b> {escape(appt.preferred_time or 'ko‘rsatilmagan')}\n"
    )
    if appt.comment:
        text += f"💬 <b>Izoh:</b> {escape(appt.comment)}\n"
    text += (
        f"\n━━━━━━━━━━━━━━━━━━━━\n"
        f"📲 Manba: {'Mini App' if appt.source == 'webapp' else 'Bot menyusi'}\n"
        f"🔗 Telegram: {escape(username or '—')}\n"
        f"🗓 Yuborildi: {fmt_date(created)}, {fmt_time(created)}\n\n"
        f"👇 Arizani tasdiqlang yoki bekor qiling — bemorga xabar avtomatik boradi."
    )
    web_app, plain = _action_markups(appt.id)
    await send(text, markup=web_app, fallback=plain)


# ─────────────────── Boshqa admin kerak bo'lgan holat ───────────────────
def _summary(history: list[dict], limit: int = 3) -> str:
    """Suhbatning qisqa ko'rinishi — butun yozishma emas.

    Shifokorning talabi: signalda butun chat kerak emas, oxirgi xabar va
    nima haqida gaplashilgani yetarli. To'liq yozishma baribir guruhdagi
    mavzuda turadi, havola bilan bir bosishda ochiladi.
    """
    tail = history[-limit * 2:] if history else []
    lines = []
    for m in tail:
        who = "👤" if m["role"] == "user" else "🤖"
        txt = m["text"].strip().replace("\n", " ")
        if len(txt) > 160:
            txt = txt[:157] + "…"
        lines.append(f"{who} {escape(txt)}")
    return "\n".join(lines)


async def escalation(
    tg_id: int | str,
    who: str,
    reason: str,
    history: list[dict],
    topic_id: int | None,
    waiting: bool,
    channel: str = "tg",
) -> None:
    """«Boshqa admin kerak» signali — ikkita tugma bilan.

    Ikkala kanal (Telegram va Instagram) uchun ham shu funksiya ishlatiladi,
    shuning uchun xabar ko'rinishi bir xil. Farq bittada: mavzuga havola
    faqat Telegramda bo'ladi — Instagram suhbatiga havola yo'q.

    `waiting=True` bo'lsa AI bemorga javob bermay javob kutyapti; admin
    tugmani bosmasa muddat tugab AI o'zi davom etadi.
    """
    from app.admin import make_esc_token
    from app.config import BASE_URL, WAIT_MINUTES
    from app.support import topic_link

    where = "Instagram" if channel == "ig" else "Telegram"
    head = (
        f"🔔 <b>BOSHQA ADMIN KERAK</b> ({where})"
        if waiting
        else f"🔔 <b>DIQQAT TALAB QILADI</b> ({where})"
    )
    body = (
        f"{head}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {escape(who)}\n"
        f"📌 {escape(reason)}\n\n"
        f"{_summary(history)}\n"
    )
    if waiting:
        body += (
            f"\n⏳ AI bu bemorga javob bermay turibdi. {WAIT_MINUTES} daqiqa "
            f"ichida tanlamasangiz, AI o'zi davom ettiradi."
        )

    key = f"{channel}:{tg_id}"
    me = (f"{BASE_URL}/admin/esc?ch={channel}&user={tg_id}&action=me"
          f"&token={make_esc_token(key, 'me')}")
    ai_ = (f"{BASE_URL}/admin/esc?ch={channel}&user={tg_id}&action=ai"
           f"&token={make_esc_token(key, 'ai')}")
    # Instagram suhbatiga havola yo'q — u yerda mavzu tushunchasi ham yo'q.
    link = topic_link(topic_id) if channel == "tg" else ""

    rows_web = [[
        {"text": "✋ Javob beraman", "web_app": {"url": me}},
        {"text": "🤖 AI davom ettirsin", "web_app": {"url": ai_}},
    ]]
    rows_plain = [[
        {"text": "✋ Javob beraman", "url": me},
        {"text": "🤖 AI davom ettirsin", "url": ai_},
    ]]
    if link:
        chat_row = [{"text": "💬 Suhbatni ochish", "url": link}]
        rows_web.append(chat_row)
        rows_plain.append(chat_row)

    await send(
        body,
        markup={"inline_keyboard": rows_web},
        fallback={"inline_keyboard": rows_plain},
    )


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


# ─────────────────────── Jonli suhbat yozuvi ───────────────────────
async def live_chat_transcript(history: list[dict], username: str, tg_id: int) -> None:
    """Jonli suhbat yakunlangach to'liq yozuvni shifokorga yuboradi.

    Suhbat bazada ham qoladi (`chat_messages.archived_at`) — bu xabar
    shifokor darhol ko'rishi uchun, baza esa tahlil uchun.
    """
    if not history:
        return

    lines = []
    for m in history:
        who = "👤" if m["role"] == "user" else "🤖"
        lines.append(f"{who} {escape(m['text'])}")

    body = "\n\n".join(lines)
    head = (
        f"🗂 <b>JONLI SUHBAT YAKUNLANDI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 {escape(username or '—')} · <code>{tg_id}</code>\n"
        f"🗓 {fmt_date(datetime.utcnow())}, {fmt_time(datetime.utcnow())}\n\n"
    )

    # Telegram cheklovi 4096 belgi — uzun suhbat bo'laklab yuboriladi.
    limit = 3800
    chunk = head
    for line in body.split("\n\n"):
        if len(chunk) + len(line) + 2 > limit:
            await send(chunk)
            chunk = ""
        chunk += line + "\n\n"
    if chunk.strip():
        await send(chunk)


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


# ─────────────────── Telefon qoldirganlar ro'yxati ───────────────────
# O'zbekiston operator kodlari. Kod ro'yxati kerak, chunki matndagi
# «168 000 000» kabi katta summa ham to'qqiz xonali bo'lib chiqadi va
# telefon raqami deb tushunilib qolardi.
_UZ_CODES = {
    "20", "33", "50", "55", "61", "62", "65", "66", "67", "69",
    "70", "71", "72", "73", "74", "75", "76", "78",
    "88", "90", "91", "93", "94", "95", "97", "98", "99",
}
_PHONE_CANDIDATE = re.compile(r"[+\d][\d\s\-()+]{7,20}\d")


def find_phones(text: str) -> list[str]:
    """Matndagi telefon raqamlari (bemor suhbatda yozib qoldirgan bo'lishi mumkin)."""
    out: list[str] = []
    for m in _PHONE_CANDIDATE.finditer(text or ""):
        digits = re.sub(r"\D", "", m.group(0))
        if digits.startswith("998"):
            digits = digits[3:]
        if len(digits) == 9 and digits[:2] in _UZ_CODES:
            num = f"+998 {digits[:2]} {digits[2:5]} {digits[5:7]} {digits[7:]}"
            if num not in out:
                out.append(num)
    return out


async def daily_contacts(days: int = 1) -> str:
    """Bugun raqam qoldirgan mijozlar — shifokorning talabi bo'yicha 22:00 da.

    Ikki manba: rasmiy arizalar va jonli suhbatda «kelaman» deb raqamini
    yozib qoldirganlar. Ikkinchisi arizaga aylanmaydi, lekin shifokor uchun
    aynan shular qimmatli — ular hech qayerda hisobga olinmasdi.
    """
    since = datetime.utcnow() - timedelta(days=days)

    async with SessionLocal() as s:
        appts = list((await s.execute(
            select(Appointment).where(Appointment.created_at >= since)
            .order_by(Appointment.created_at)
        )).scalars())
        msgs = list((await s.execute(
            select(ChatMessage)
            .where(ChatMessage.created_at >= since, ChatMessage.role == "user")
            .order_by(ChatMessage.created_at)
        )).scalars())
        users = {
            u.tg_id: u for u in (await s.execute(select(User))).scalars() if u.tg_id
        }

    appt_phones = {re.sub(r"\D", "", a.phone or "")[-9:] for a in appts}

    # Suhbatda raqam yozganlar — arizada bori takrorlanmaydi.
    from_chat: dict[str, list[str]] = {}
    for m in msgs:
        for phone in find_phones(m.text):
            if re.sub(r"\D", "", phone)[-9:] in appt_phones:
                continue
            u = users.get(m.tg_id)
            who = " ".join(
                x for x in ((u.first_name if u else ""), (u.last_name if u else "")) if x
            ).strip()
            if u and u.username:
                who = f"{who} (@{u.username})".strip()
            from_chat.setdefault(phone, [])
            label = who or f"id{m.tg_id}"
            if label not in from_chat[phone]:
                from_chat[phone].append(label)

    now = datetime.utcnow()
    lines = [
        "📞 <b>BUGUN RAQAM QOLDIRGANLAR</b>",
        f"🗓 {fmt_date(now)}",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    if appts:
        lines.append(f"\n📅 <b>Ariza qoldirganlar — {len(appts)} ta</b>")
        for a in appts:
            lines.append(
                f"\n<b>{escape(a.full_name)}</b>\n"
                f"   📱 <code>{escape(a.phone)}</code>\n"
                f"   🕐 {escape(a.preferred_time or 'vaqt ko‘rsatilmagan')}"
            )

    if from_chat:
        lines.append(f"\n\n💬 <b>Suhbatda raqam yozganlar — {len(from_chat)} ta</b>")
        lines.append("<i>Bular ariza qoldirmagan — o'zingiz bog'lanishingiz kerak.</i>")
        for phone, whos in from_chat.items():
            lines.append(f"\n<b>{escape(', '.join(whos))}</b>\n   📱 <code>{phone}</code>")

    if not appts and not from_chat:
        lines.append("\nBugun hech kim raqam qoldirmadi.")

    text = "\n".join(lines)
    for chunk in [text[i:i + 3900] for i in range(0, len(text), 3900)]:
        await send(chunk)
    return text


# ─────────────────────────── Kunlik jadval ───────────────────────────
# (Toshkent vaqti bilan soat, vazifa nomi, funksiya)
DAILY_JOBS: list[tuple[int, str, object]] = [
    (20, "kunlik xulosa", lambda: daily_summary()),
    (22, "raqam qoldirganlar", lambda: daily_contacts()),
]

DAILY_HOUR_LOCAL = 20  # eski nom — tashqi skriptlar ishlatishi mumkin


async def daily_scheduler() -> None:
    """Belgilangan soatlarda kunlik xabarlarni yuboradi.

    Servis uyquda bo'lsa o'sha vazifa o'tkazib yuboriladi — shuning uchun
    `/health` ni tashqi cron bilan uyg'oq tutish tavsiya etiladi.
    """
    import asyncio

    from app.bot.calendar import TZ_OFFSET

    while True:
        now = datetime.utcnow() + TZ_OFFSET
        # Eng yaqin vazifani tanlaymiz.
        best: tuple[datetime, str, object] | None = None
        for hour, name, job in DAILY_JOBS:
            target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            if best is None or target < best[0]:
                best = (target, name, job)

        target, name, job = best  # type: ignore[misc]
        await asyncio.sleep((target - now).total_seconds())
        try:
            await job()  # type: ignore[operator]
        except Exception as e:
            log.warning("«%s» yuborilmadi: %s", name, e)
        # Bir daqiqa kutamiz, aks holda o'sha soat ichida qayta ishga tushadi.
        await asyncio.sleep(61)
