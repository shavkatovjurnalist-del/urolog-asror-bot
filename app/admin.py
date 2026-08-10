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
