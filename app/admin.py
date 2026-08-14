"""Ariza tasdiqlash/bekor qilish — hisobot botidagi tugmalar shu sahifani ochadi.

Nima uchun shunday: hisobot boti (@ai_humoyunbot) ning webhook'i boshqa loyihaga
ulangan va unga tegib bo'lmaydi. Shuning uchun tugmalar callback yubormaydi,
balki shu servisdagi imzolangan sahifani ochadi (Telegram ichida, Mini App
oynasida). Sahifa amalni bajaradi va bemorga xabar yuboradi.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app import repo
from app.bot import texts as t
from app.config import WEBHOOK_SECRET
from app.db import SessionLocal
from app.models import Appointment

log = logging.getLogger(__name__)
router = APIRouter(prefix="/admin")

ACTIONS = {"confirm", "cancel"}


def make_token(appt_id: int, action: str) -> str:
    msg = f"{appt_id}:{action}".encode()
    return hmac.new(WEBHOOK_SECRET.encode(), msg, hashlib.sha256).hexdigest()[:32]


def check_token(appt_id: int, action: str, token: str) -> bool:
    return hmac.compare_digest(make_token(appt_id, action), token or "")


def make_esc_token(key: int | str, action: str) -> str:
    """Signal tugmalari uchun imzo. `key` — «kanal:foydalanuvchi»."""
    msg = f"esc:{key}:{action}".encode()
    return hmac.new(WEBHOOK_SECRET.encode(), msg, hashlib.sha256).hexdigest()[:32]


def _page(title: str, body: str, color: str) -> HTMLResponse:
    html = f"""<!DOCTYPE html>
<html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
  body {{ margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center;
         font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
         background:var(--tg-theme-secondary-bg-color,#f2f5f6);
         color:var(--tg-theme-text-color,#0e1a19); padding:24px; }}
  .box {{ background:var(--tg-theme-bg-color,#fff); border-radius:18px; padding:32px 24px;
          text-align:center; max-width:380px; width:100%;
          box-shadow:0 2px 18px rgba(10,40,38,.08); }}
  .ico {{ font-size:52px; }}
  h1 {{ font-size:19px; margin:14px 0 8px; color:{color}; }}
  p {{ font-size:14px; line-height:1.55; color:var(--tg-theme-hint-color,#6b7b7a); margin:0; }}
  button {{ margin-top:22px; width:100%; padding:13px; border:none; border-radius:12px;
            background:{color}; color:#fff; font-size:15px; font-weight:600; cursor:pointer; }}
</style></head>
<body><div class="box">{body}
<button onclick="Telegram.WebApp.close()">Yopish</button></div>
<script>try{{Telegram.WebApp.ready();Telegram.WebApp.expand();}}catch(e){{}}</script>
</body></html>"""
    return HTMLResponse(html)


ESC_ACTIONS = {"me", "ai"}


@router.get("/esc")
async def escalation_action(
    action: str, user: str = "", ch: str = "tg", tg: int | None = None, token: str = ""
) -> HTMLResponse:
    """«Javob beraman» / «AI davom ettirsin» tugmalari shu yerga tushadi.

    Ikkala kanal uchun ham shu yo'l: `ch=tg` — bu servisning o'z bazasi,
    `ch=ig` — Instagram tizimining bazasi (`app/ig_bridge.py`).

    Nima uchun tugma callback emas, havola: signal @ai_humoyunbot orqali
    ketadi, uning webhook'i esa boshqa loyihaga ulangan — callback'ni bu
    servis umuman ko'rmaydi. Arizalarni tasdiqlashda ham xuddi shu yo'l.
    """
    if action not in ESC_ACTIONS:
        raise HTTPException(400, "Noma'lum amal")
    if ch not in {"tg", "ig"}:
        raise HTTPException(400, "Noma'lum kanal")

    uid = user or (str(tg) if tg is not None else "")
    if not uid:
        raise HTTPException(400, "Foydalanuvchi ko'rsatilmagan")
    if not hmac.compare_digest(make_esc_token(f"{ch}:{uid}", action), token or ""):
        raise HTTPException(403, "Imzo noto'g'ri")

    from app.config import HUMAN_PAUSE_MINUTES

    # Guruhdagi signal xabarining tugmalari natija yozuviga almashtiriladi —
    # aks holda ular bosilmagandek turaverardi va ikkinchi admin qayta
    # bosishi mumkin edi (shifokorning talabi, 2026-08-14).
    from app import report
    natija = ("✅ Qabul qilindi — javobni admin yozadi" if action == "me"
              else "✅ Qabul qilindi — AI davom ettiradi")
    try:
        await report.signal_tugmasini_yangila(ch, uid, natija)
    except Exception as e:
        log.warning("Signal tugmasini yangilab bo'lmadi: %s", e)

    if ch == "ig":
        return await _esc_instagram(uid, action, HUMAN_PAUSE_MINUTES)
    return await _esc_telegram(int(uid), action, HUMAN_PAUSE_MINUTES)


async def _esc_telegram(tg_id: int, action: str, pause: int) -> HTMLResponse:
    from app import support
    from app.bot.instance import bot

    async with SessionLocal() as s:
        th = await support.get_thread(s, tg_id)
        already = th.mode if th else None

    if action == "me":
        await support.set_mode(tg_id, "human")
        await support.notify(
            bot, tg_id, "✋ <b>Admin javob beradi</b> — AI bu suhbatda jim turadi."
        )
        return _page(
            "Sizga topshirildi",
            f'<div class="ico">✋</div><h1>Javobni siz yozasiz</h1>'
            f"<p>AI bu bemorga {pause} daqiqa javob bermaydi. "
            f"Guruhdagi mavzuga yozgan xabaringiz bemorga boradi.</p>",
            "#b8860b",
        )

    await support.set_mode(tg_id, "ai")
    await support.notify(bot, tg_id, "🤖 <b>AI davom ettiradi</b> — pauza bekor qilindi.")
    sent = False
    try:
        await bot.send_message(
            tg_id,
            "Rahmat, kutganingiz uchun. Savolingizni davom ettiraylik — "
            "yana nimani bilmoqchi edingiz?\n\n"
            "Agar xohlasangiz, telefon raqamingizni yozib qoldiring — "
            "o'zlari siz bilan bog'lanishadi.",
        )
        sent = True
    except Exception as e:
        log.warning("Bemorga (%s) davom xabari ketmadi: %s", tg_id, e)

    note = (
        "Bemorga suhbat davom etayotgani haqida xabar yuborildi."
        if sent
        else "Bemorga xabar yuborilmadi — u botni bloklagan bo'lishi mumkin."
    )
    if already == "ai":
        note = "Bu suhbat allaqachon AI da edi. " + note
    return _page(
        "AI davom ettiradi",
        f'<div class="ico">🤖</div><h1>AI javob berishda davom etadi</h1><p>{note}</p>',
        "#007a70",
    )


async def _esc_instagram(user_id: str, action: str, pause: int) -> HTMLResponse:
    """Instagram tomonida bu servisning bemorga to'g'ridan-to'g'ri yo'li yo'q.

    Shuning uchun faqat rejim o'zgartiriladi: javobni admin Instagram'ning
    o'z suhbatidan yozadi. AI davom etganda ham xabarni mijoz keyingi marta
    yozganda n8n beradi — Instagramda javobsiz xabar yuborilmaydi.
    """
    from app import ig_bridge

    if not ig_bridge.enabled():
        raise HTTPException(503, "Instagram bazasi ulanmagan")

    if action == "me":
        await ig_bridge.set_mode(user_id, "human")
        return _page(
            "Sizga topshirildi",
            f'<div class="ico">✋</div><h1>Javobni siz yozasiz</h1>'
            f"<p>AI bu mijozga {pause} daqiqa javob bermaydi. "
            f"Instagramdagi suhbatga o'zingiz yozing — tizim buni sezadi "
            f"va AI jim turaveradi.</p>",
            "#b8860b",
        )

    await ig_bridge.set_mode(user_id, "ai")
    return _page(
        "AI davom ettiradi",
        '<div class="ico">🤖</div><h1>AI javob berishda davom etadi</h1>'
        "<p>Kutish bekor qilindi. Mijoz keyingi marta yozganda AI odatdagidek "
        "javob beradi — Instagramda javobsiz xabar yuborilmaydi.</p>",
        "#007a70",
    )


@router.get("/appt")
async def appt_action(id: int, action: str, token: str = "") -> HTMLResponse:
    if action not in ACTIONS:
        raise HTTPException(400, "Noma'lum amal")
    if not check_token(id, action, token):
        raise HTTPException(403, "Imzo noto'g'ri")

    async with SessionLocal() as s:
        appt = await s.get(Appointment, id)
        if not appt:
            raise HTTPException(404, "Ariza topilmadi")

        already = appt.status in ("confirmed", "cancelled")
        prev_status = appt.status
        if not already:
            appt.status = "confirmed" if action == "confirm" else "cancelled"
            await s.commit()

        clinic = await repo.get_clinic(s, appt.clinic_id) if appt.clinic_id else None
        clinic_name = clinic.name if clinic else "Klinika qabulda aniqlanadi"
        tg_id, when = appt.tg_id, appt.preferred_time

    if already:
        label = "tasdiqlangan" if prev_status == "confirmed" else "bekor qilingan"
        return _page(
            "Allaqachon ko'rilgan",
            f'<div class="ico">ℹ️</div><h1>Ariza №{id} allaqachon {label}</h1>'
            f"<p>Bu ariza ustida amal bajarilgan, o'zgarish kiritilmadi.</p>",
            "#6b7b7a",
        )

    # Bemorga xabar
    sent = False
    if tg_id:
        from app.bot.instance import bot

        try:
            text = (
                t.appointment_confirmed(id, when, clinic_name)
                if action == "confirm"
                else t.appointment_rejected(id, when)
            )
            await bot.send_message(tg_id, text)
            sent = True
        except Exception as e:
            log.warning("Bemorga xabar yuborilmadi (%s): %s", tg_id, e)

    note = (
        "Bemorga xabar yuborildi."
        if sent
        else "Bemorga xabar yuborilmadi — u botni bloklagan yoki Mini App orqali "
             "anonim yozgan bo'lishi mumkin. Telefon orqali bog'laning."
    )

    if action == "confirm":
        return _page(
            "Tasdiqlandi",
            f'<div class="ico">✅</div><h1>Ariza №{id} tasdiqlandi</h1><p>{note}</p>',
            "#007a70",
        )
    return _page(
        "Bekor qilindi",
        f'<div class="ico">❌</div><h1>Ariza №{id} bekor qilindi</h1><p>{note}</p>',
        "#c0392b",
    )
