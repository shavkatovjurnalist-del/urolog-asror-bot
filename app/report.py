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


async def send(text: str, markup: dict | None = None,
               fallback: dict | None = None) -> list[tuple[str, int]]:
    """Hisobot matnini barcha qabul qiluvchilarga yuboradi.

    `markup` — inline tugmalar. Telegram uni rad etsa (masalan Web App tugmasi
    qo'llab-quvvatlanmasa) `fallback` bilan qayta uriniladi.

    Qaytaradi: yuborilgan xabarlarning `(chat_id, message_id)` ro'yxati —
    eskalatsiya signalida tugma bosilgach o'sha xabarni tahrirlash uchun
    kerak («✋ Javob beraman» -> «✅ Javobni siz yozasiz»). Busiz admin
    tugmani bosgan-bosmaganini xabarning o'zidan bilolmasdi.
    """
    if not REPORT_BOT_TOKEN or not REPORT_CHAT_IDS:
        log.info("Hisobot boti sozlanmagan — yuborilmadi.")
        return []

    yuborilgan: list[tuple[str, int]] = []
    url = f"https://api.telegram.org/bot{REPORT_BOT_TOKEN}/sendMessage"

    def _qayd(chat_id, javob) -> bool:
        try:
            d = javob.json()
        except Exception:
            return False
        if not d.get("ok"):
            return False
        mid = (d.get("result") or {}).get("message_id")
        if mid:
            yuborilgan.append((str(chat_id), int(mid)))
        return True

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
                if _qayd(chat_id, r):
                    continue
                log.warning("Hisobot yuborilmadi (%s): %s", chat_id, r.text[:200])
                if fallback:
                    payload["reply_markup"] = fallback
                    r2 = await client.post(url, json=payload)
                    if not _qayd(chat_id, r2):
                        payload.pop("reply_markup", None)
                        r3 = await client.post(url, json=payload)
                        _qayd(chat_id, r3)
            except Exception as e:
                log.warning("Hisobot xatosi (%s): %s", chat_id, e)
    return yuborilgan


async def signal_tugmasini_yangila(kanal: str, uid: str, natija: str) -> None:
    """Eskalatsiya signalidagi tugmalarni natija yozuviga almashtiradi.

    Admin «✋ Javob beraman» yoki «🤖 AI davom ettirsin» ni bosganda natija
    Web App oynasida ko'rinardi, lekin GURUHDAGI xabar o'zgarishsiz
    qolardi: keyin kim qarasa, tugmalar hali ham bosilmagandek turardi va
    ikkinchi admin qayta bosishi mumkin edi.

    Endi ikkala tugma o'rniga bitta yozuv qoladi — masalan
    «✅ Qabul qilindi — javobni admin yozadi».

    Nima uchun `editMessageReplyMarkup`, `editMessageText` emas: matnni
    qayta yuborish uchun uni biror joyda saqlash kerak bo'lardi, xabar esa
    500+ belgi (`Setting.value` — 255). Tugmani almashtirish uchun faqat
    xabar manzili yetadi.

    `message_id` `send()` dan olinib `bot.settings` ga yozilgan bo'ladi.
    """
    from app.repo import get_setting, set_setting

    kalit = f"esc_msg:{kanal}:{uid}"
    saqlangan = await get_setting(kalit, "")
    if not saqlangan or not REPORT_BOT_TOKEN:
        return

    from app.config import BASE_URL

    # Telegram inline tugmasi `url` siz bo'lolmaydi, shuning uchun zararsiz
    # manzil qo'yiladi — tugma endi faqat YOZUV vazifasini bajaradi.
    markup = {"inline_keyboard": [[{"text": natija, "url": f"{BASE_URL}/health"}]]}
    url = f"https://api.telegram.org/bot{REPORT_BOT_TOKEN}/editMessageReplyMarkup"
    async with httpx.AsyncClient(timeout=20) as client:
        for juftlik in saqlangan.split("|"):
            if ":" not in juftlik:
                continue
            chat_id, _, mid = juftlik.rpartition(":")
            try:
                await client.post(url, json={
                    "chat_id": chat_id,
                    "message_id": int(mid),
                    "reply_markup": markup,
                })
            except Exception as e:
                log.warning("Signal tugmasini yangilab bo'lmadi: %s", e)
    # Bir marta ishlatiladi — keyingi signalda yangisi yoziladi.
    await set_setting(kalit, "")


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

    yuborilgan = await send(
        body,
        markup={"inline_keyboard": rows_web},
        fallback={"inline_keyboard": rows_plain},
    )

    # Tugma bosilganda shu xabarning ostiga natija yoziladi va tugmalar
    # olib tashlanadi (`signal_xabarini_yangila`). Buning uchun xabar
    # manzili va asl matni saqlanadi — ikkalasi ham `bot.settings` da,
    # chunki eskalatsiya TG tomonida jadvalga yozilmaydi.
    if yuborilgan:
        from app.repo import set_setting
        await set_setting(f"esc_msg:{channel}:{tg_id}",
                          "|".join(f"{c}:{m}" for c, m in yuborilgan)[:255])


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


async def daily_contacts(hours: int = 12) -> str:
    """Oxirgi N soatda raqam qoldirgan mijozlar.

    Shifokorning talabi (2026-08-14): kuniga IKKI MARTA — ertalab 08:00 va
    kechqurun 20:00, har biri oldingi 12 soatlik oraliqni qamraydi. Ilgari
    kuniga bir marta 22:00 da yuborilardi: kechqurun yozgan mijoz ertasi
    kuni ko'rilardi va bog'lanish bir sutkaga kechikardi.

    TO'RT manba — raqam qoldirishning hamma yo'li:
      1. rasmiy ariza (`Appointment`);
      2. botda yoki Mini App'da ro'yxatdan o'tib kontakt bergan (`User.phone`)
         — 2026-08-14 gacha bu manba ro'yxatga UMUMAN kirmasdi;
      3. Telegram suhbatida raqamini yozib qoldirgan (`ChatMessage`);
      4. Instagram Direct'da raqam yozgan (`ig_bridge`).

    Takrorlanish yo'q: bir raqam bir marta ko'rsatiladi, eng «rasmiy»
    manbasi bo'yicha (ariza > ro'yxat > suhbat > Instagram).
    """
    since = datetime.utcnow() - timedelta(hours=hours)

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
        # Ro'yxatdan o'tib kontakt bergan — shu oraliqda kelganlar.
        yangi_users = list((await s.execute(
            select(User).where(User.created_at >= since, User.phone != "")
            .order_by(User.created_at)
        )).scalars())

    appt_phones = {re.sub(r"\D", "", a.phone or "")[-9:] for a in appts}

    # 2-manba: ro'yxatdan o'tganlar. Arizada bori takrorlanmaydi.
    from_reg: dict[str, list[str]] = {}
    for u in yangi_users:
        oxirgi9 = re.sub(r"\D", "", u.phone or "")[-9:]
        if not oxirgi9 or oxirgi9 in appt_phones:
            continue
        who = " ".join(x for x in (u.first_name, u.last_name) if x).strip()
        if u.username:
            who = f"{who} (@{u.username})".strip()
        label = who or f"id{u.tg_id}"
        from_reg.setdefault(u.phone, [])
        if label not in from_reg[u.phone]:
            from_reg[u.phone].append(label)
    reg_phones = {re.sub(r"\D", "", p)[-9:] for p in from_reg}

    # Suhbatda raqam yozganlar — ariza va ro'yxatda bori takrorlanmaydi.
    from_chat: dict[str, list[str]] = {}
    for m in msgs:
        for phone in find_phones(m.text):
            oxirgi9 = re.sub(r"\D", "", phone)[-9:]
            if oxirgi9 in appt_phones or oxirgi9 in reg_phones:
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

    # Instagram tomoni. 2026-08-13 gacha bu ro'yxat faqat Telegram
    # manbalaridan yig'ilardi va Instagramda raqam qoldirgan mijoz hech
    # qayerda ko'rinmasdi — shifokor uni butunlay yo'qotardi.
    from app import ig_bridge

    from_ig: dict[str, list[str]] = {}
    chat_phones = {re.sub(r"\D", "", p)[-9:] for p in from_chat}
    try:
        for m in await ig_bridge.recent_user_messages(hours=hours):
            for phone in find_phones(m["text"]):
                oxirgi9 = re.sub(r"\D", "", phone)[-9:]
                if oxirgi9 in appt_phones or oxirgi9 in reg_phones \
                        or oxirgi9 in chat_phones:
                    continue
                label = m["who"] or f"ig:{m['user_id']}"
                from_ig.setdefault(phone, [])
                if label not in from_ig[phone]:
                    from_ig[phone].append(label)
    except Exception as ex:
        log.warning("Instagram raqamlarini o'qib bo'lmadi: %s", ex)

    from app.bot.calendar import TZ_OFFSET

    now = datetime.utcnow()
    boshi = (since + TZ_OFFSET).strftime("%H:%M")
    oxiri = (now + TZ_OFFSET).strftime("%H:%M")
    lines = [
        "📞 <b>RAQAM QOLDIRGANLAR</b>",
        f"🗓 {fmt_date(now)} · <b>{boshi} – {oxiri}</b> oralig‘i",
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

    if from_reg:
        lines.append(f"\n\n📝 <b>Ro‘yxatdan o‘tganlar — {len(from_reg)} ta</b>")
        lines.append("<i>Botda yoki Mini App'da kontakt bergan, ariza qoldirmagan.</i>")
        for phone, whos in from_reg.items():
            lines.append(f"\n<b>{escape(', '.join(whos))}</b>\n   📱 <code>{escape(phone)}</code>")

    if from_chat:
        lines.append(f"\n\n💬 <b>Telegram suhbatida raqam yozganlar — "
                     f"{len(from_chat)} ta</b>")
        lines.append("<i>Bular ariza qoldirmagan — o'zingiz bog'lanishingiz kerak.</i>")
        for phone, whos in from_chat.items():
            lines.append(f"\n<b>{escape(', '.join(whos))}</b>\n   📱 <code>{phone}</code>")

    if from_ig:
        lines.append(f"\n\n📸 <b>Instagramda raqam yozganlar — {len(from_ig)} ta</b>")
        lines.append("<i>Direct orqali yozganlar — ariza qoldirmagan.</i>")
        for phone, whos in from_ig.items():
            lines.append(f"\n<b>{escape(', '.join(whos))}</b>\n   📱 <code>{phone}</code>")

    if appts or from_reg or from_chat or from_ig:
        jami = len(appts) + len(from_reg) + len(from_chat) + len(from_ig)
        lines.append(f"\n\n━━━━━━━━━━━━━━━━━━━━\n<b>Jami ehtimoliy mijoz: "
                     f"{jami} ta</b>")
    else:
        lines.append(f"\n{boshi} – {oxiri} oralig‘ida hech kim raqam qoldirmadi.")

    text = "\n".join(lines)
    for chunk in [text[i:i + 3900] for i in range(0, len(text), 3900)]:
        await send(chunk)
    return text


async def daily_stats(hours: int = 24) -> str:
    """Kun yakuni — QISQA raqamlar (shifokorning talabi, 22:00).

    «Raqam qoldirganlar» ro'yxati (08:00 va 20:00) — bu KIM bilan
    bog'lanish kerakligi. Bu esa boshqa savolga javob beradi: kun qanday
    o'tdi. Shuning uchun tafsilot yo'q, faqat sonlar:

      · nechta odam yozdi — jami, Telegram va Instagram alohida;
      · nechtasi raqam qoldirdi;
      · nechta rasmiy ariza tushdi.

    Odamlar SANALADI, xabarlar emas: bitta bemor 20 marta yozsa ham u
    bitta odam.
    """
    since = datetime.utcnow() - timedelta(hours=hours)

    async with SessionLocal() as s:
        tg_odam = (await s.execute(
            select(func.count(func.distinct(ChatMessage.tg_id)))
            .where(ChatMessage.created_at >= since, ChatMessage.role == "user")
        )).scalar() or 0
        appts = list((await s.execute(
            select(Appointment).where(Appointment.created_at >= since)
        )).scalars())
        yangi_user = (await s.execute(
            select(func.count(User.id)).where(User.created_at >= since)
        )).scalar() or 0
        reg_phone = (await s.execute(
            select(func.count(User.id))
            .where(User.created_at >= since, User.phone != "")
        )).scalar() or 0
        msgs = list((await s.execute(
            select(ChatMessage)
            .where(ChatMessage.created_at >= since, ChatMessage.role == "user")
        )).scalars())

    # Telegram suhbatida raqam yozganlar (arizadagilar takrorlanmaydi)
    appt_phones = {re.sub(r"\D", "", a.phone or "")[-9:] for a in appts}
    tg_raqam: set[str] = set()
    for m in msgs:
        for phone in find_phones(m.text):
            oxirgi9 = re.sub(r"\D", "", phone)[-9:]
            if oxirgi9 and oxirgi9 not in appt_phones:
                tg_raqam.add(oxirgi9)

    # Instagram tomoni
    from app import ig_bridge

    ig_odam, ig_raqam = 0, set()
    try:
        ig_msgs = await ig_bridge.recent_user_messages(hours=hours)
        ig_odam = len({m["user_id"] for m in ig_msgs})
        for m in ig_msgs:
            for phone in find_phones(m["text"]):
                oxirgi9 = re.sub(r"\D", "", phone)[-9:]
                if oxirgi9:
                    ig_raqam.add(oxirgi9)
    except Exception as ex:
        log.warning("Instagram statistikasi olinmadi: %s", ex)

    jami_odam = tg_odam + ig_odam
    jami_raqam = len(tg_raqam | ig_raqam) + len(appt_phones - {""}) + reg_phone

    now = datetime.utcnow()
    lines = [
        "🌙 <b>KUN YAKUNI</b>",
        f"🗓 {fmt_date(now)} · oxirgi {hours} soat",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"👥 <b>Yozgan odamlar: {jami_odam} ta</b>",
        f"   💬 Telegram — {tg_odam} ta",
        f"   📸 Instagram — {ig_odam} ta",
        "",
        f"📞 <b>Raqam qoldirganlar: {jami_raqam} ta</b>",
        f"   📝 Ariza — {len(appts)} ta",
        f"   👤 Ro‘yxatdan o‘tib kontakt bergan — {reg_phone} ta",
        f"   💬 Telegram suhbatida — {len(tg_raqam)} ta",
        f"   📸 Instagram Direct'da — {len(ig_raqam)} ta",
        "",
        f"🆕 Yangi foydalanuvchi: {yangi_user} ta",
    ]
    if jami_odam == 0:
        lines.append("\n<i>Bugun murojaat bo‘lmadi.</i>")

    text = "\n".join(lines)
    await send(text)
    return text


async def eski_yozishmalarni_tozalash(kun: int = 365) -> int:
    """1 yildan eski yozishmalarni o'chiradi.

    Nima uchun: Meta Platform Terms ma'lumotni «kerakli muddatdan uzoq
    saqlamaslikni» talab qiladi, bu jadval esa 2026-08-14 gacha umuman
    tozalanmasdi. AI xotirasi uchun bir yil ortig'i bilan yetadi —
    kontekstga faqat oxirgi bir necha xabar olinadi, o'qitish uchun esa
    suhbatlar `AI_brain/chatlar/` ga eksport qilinadi (kunlik, avtomat).

    `users`, `appointments`, `consultations` TEGILMAYDI: ular mijoz
    tarixi va buxgalteriya, xabar emas.

    Instagram tomonida xuddi shu ish `tokenCheck0001` workflow'ida.
    """
    from sqlalchemy import delete

    chegara = datetime.utcnow() - timedelta(days=kun)
    async with SessionLocal() as s:
        r = await s.execute(
            delete(ChatMessage).where(ChatMessage.created_at < chegara))
        await s.commit()
    n = r.rowcount or 0
    if n:
        log.info("Arxiv tozalandi: %s ta eski xabar o'chirildi (%s kundan eski)", n, kun)
    return n


# ─────────────────────────── Kunlik jadval ───────────────────────────
#  (Toshkent vaqti bilan soat, daqiqa, vazifa nomi, funksiya)
#
#  «Raqam qoldirganlar» kuniga IKKI MARTA yuboriladi — shifokorning talabi
#  (2026-08-14). Har biri oldingi 12 soatni qamraydi:
#     08:00 -> kechagi 20:00 dan bugungi 08:00 gacha
#     20:00 -> bugungi 08:00 dan 20:00 gacha
#  Ilgari kuniga bir marta 22:00 da edi va kechqurun yozgan mijoz bilan
#  ertasi kuni bog'lanilardi.
#  22:00 — kun yakuni: QISQA raqamlar (nechta odam yozdi, TG/IG alohida,
#  nechtasi raqam qoldirdi). Ilgari bu o'rinda `daily_summary` 20:00 da
#  turardi; endi 20:00 raqamlar ro'yxatiga ajratilgan va tafsilotli
#  xulosa ham kun yakuniga ko'chirilgan — ikkovi ketma-ket keladi.
DAILY_JOBS: list[tuple[int, int, str, object]] = [
    (8,  0, "raqam qoldirganlar (kechasi)",  lambda: daily_contacts(hours=12)),
    (20, 0, "raqam qoldirganlar (kunduzi)",  lambda: daily_contacts(hours=12)),
    (22, 0, "kun yakuni — qisqa raqamlar",   lambda: daily_stats(hours=24)),
    (22, 2, "kunlik xulosa (arizalar)",      lambda: daily_summary()),
    # Eng kam yuklama vaqtida — 1 yildan eski yozishmalar o'chiriladi.
    (3,  0, "eski yozishmalarni tozalash",   lambda: eski_yozishmalarni_tozalash(365)),
]

DAILY_HOUR_LOCAL = 20  # eski nom — tashqi skriptlar ishlatishi mumkin


async def daily_scheduler() -> None:
    """Belgilangan vaqtlarda kunlik xabarlarni yuboradi.

    Servis uyquda bo'lsa o'sha vazifa o'tkazib yuboriladi — shuning uchun
    `/health` ni tashqi cron bilan uyg'oq tutish tavsiya etiladi.

    ⚠️ Ilgari bu sikl faqat ENG YAQIN bitta vazifani bajarardi va undan
    keyin 61 soniya kutardi. Natijada bir soatga ikkita vazifa qo'yilsa
    (masalan 20:00 da xulosa va raqamlar ro'yxati) ikkinchisi o'sha kuni
    UMUMAN yuborilmasdi — sikl qaytganda o'sha vaqt allaqachon o'tgan
    bo'lardi va u ertangi kunga suriladi. Shu sababdan vazifalar
    daqiqa bilan beriladi va har biri alohida navbatda bajariladi.
    """
    import asyncio

    from app.bot.calendar import TZ_OFFSET

    while True:
        now = datetime.utcnow() + TZ_OFFSET
        best: tuple[datetime, str, object] | None = None
        for hour, minute, name, job in DAILY_JOBS:
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            if best is None or target < best[0]:
                best = (target, name, job)

        target, name, job = best  # type: ignore[misc]
        kutish = (target - now).total_seconds()
        log.info("keyingi kunlik vazifa: «%s» %s da (%.0f daqiqadan keyin)",
                 name, target.strftime("%H:%M"), kutish / 60)
        await asyncio.sleep(kutish)
        try:
            await job()  # type: ignore[operator]
        except Exception as e:
            log.warning("«%s» yuborilmadi: %s", name, e)
        # Bir daqiqadan kamroq kutamiz: keyingi vazifa 2 daqiqadan keyin
        # bo'lishi mumkin (20:00 va 20:02), lekin o'sha soniyada qayta
        # ishga tushib ketmasligi ham kerak.
        await asyncio.sleep(31)
