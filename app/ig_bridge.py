"""Instagram tizimi bilan ko'prik.

Instagram tomonini n8n yuritadi va u **boshqa bazada** yashaydi (`bot`
sxemasi). Shu paytgacha Instagram signallarini n8n o'zi Telegramga
yuborardi — natijada ikkita boshqa-boshqa ko'rinishdagi xabar bo'lardi:
Telegramniki tugmali, Instagramniki oddiy matn.

Endi signalni **ikkala kanal uchun ham shu servis** yuboradi: n8n faqat
`bot.escalations` jadvaliga yozadi, biz uni kuzatib turamiz. Foydasi:
  • xabar ko'rinishi va tugmalari bir xil;
  • tugma bosilganda AI ni to'xtatish/qaytarish mantiqi ham bitta joyda;
  • n8n workflow'iga tegilmaydi.

`IG_DATABASE_URL` bo'sh bo'lsa modul butunlay jim turadi — Telegram
tomoni avvalgidek ishlayveradi.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app.config import HUMAN_PAUSE_MINUTES, IG_DATABASE_URL, WAIT_MINUTES

log = logging.getLogger(__name__)

_pool = None


def enabled() -> bool:
    return bool(IG_DATABASE_URL)


async def _conn():
    """Ulanishlar hovuzi — Neon bo'sh ulanishlarni uzadi, shuning uchun kichik."""
    global _pool
    if _pool is None:
        import asyncpg

        _pool = await asyncpg.create_pool(
            IG_DATABASE_URL, min_size=0, max_size=2, ssl=True,
            max_inactive_connection_lifetime=120,
        )
    return _pool


async def close() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


# ─────────────────────── Signal uchun ma'lumot ───────────────────────
# n8n qaytaradigan sabab kodlari — signalda o'zbekcha ko'rinadi.
REASONS = {
    "escalate_rule": "Bemor boshqa admin so'radi",
    "ai_escalate": "AI javob berolmadi",
    "media_received": "Rasm / ovozli xabar yuborildi",
    "urgent": "🚨 SHOSHILINCH",
    "never_say": "AI taqiqlangan narsani yozdi",
    "never_say_link": "AI havola yozmoqchi bo'ldi",
    "empty_reply": "AI javobi bo'sh chiqdi",
    "fact_not_in_kb": "Bilim bazasida yo'q fakt so'raldi",
    "window_expired_24h": "24 soatlik oyna yopilgan",
    "rate_limit_hour": "Soatlik limit to'ldi",
    "rate_limit_day": "Kunlik limit to'ldi",
    "human_detected": "Suhbatga odam javob yozdi",
}


def reason_text(code: str) -> str:
    return REASONS.get(code or "", code or "Noma'lum sabab")


async def fetch_new_escalations(limit: int = 10) -> list[dict]:
    """Hali yuborilmagan signallar. Qaytarilishi bilan belgilanadi.

    `notified` bayrog'i shu yerda qo'yiladi: xabar yuborishda xato bo'lsa
    ham ikkinchi marta urinilmaydi — takroriy signal shovqinidan yomoni yo'q.

    `pending_since` ham olinadi: shu bo'yicha AI javob kutayotgani (ya'ni
    xabarda «AI javob bermay turibdi» yozuvi kerakligi) aniqlanadi.
    """
    if not enabled():
        return []
    pool = await _conn()
    async with pool.acquire() as c:
        rows = await c.fetch(
            """
            WITH picked AS (
                UPDATE bot.escalations SET notified = TRUE
                 WHERE id IN (
                    SELECT id FROM bot.escalations
                     WHERE notified = FALSE AND channel = 'instagram'
                     ORDER BY id LIMIT $1
                 )
                RETURNING id, user_id, reason, severity, user_text
            )
            SELECT p.*, c.pending_since
              FROM picked p
              LEFT JOIN bot.conversations c
                ON c.channel = 'instagram' AND c.user_id = p.user_id
             ORDER BY p.id
            """,
            limit,
        )
    return [dict(r) for r in rows]


async def escalation_watcher() -> None:
    """Instagram signallarini Telegramga uzatadi — Telegramnikiga o'xshash.

    Ilgari bu xabarni n8n o'zi yuborardi va u tugmasiz, boshqacha
    ko'rinishda edi. Endi ikkala kanal ham `report.escalation` orqali
    o'tadi, ya'ni ko'rinish va tugmalar bir xil.
    """
    import asyncio

    from app import report

    if not enabled():
        return
    while True:
        await asyncio.sleep(30)
        try:
            for e in await fetch_new_escalations():
                uid = str(e["user_id"])
                await report.escalation(
                    tg_id=uid,
                    who=await contact_name(uid),
                    reason=reason_text(e["reason"]),
                    history=await recent_messages(uid),
                    topic_id=None,
                    waiting=e["pending_since"] is not None,
                    channel="ig",
                )
        except Exception as ex:
            log.warning("Instagram signal kuzatuvchisi xatosi: %s", ex)


async def contact_name(user_id: str) -> str:
    """Mijozning ismi va @username — signalda shular ko'rsatiladi.

    Profil `ig-profile-merge.js` da Graph API dan olinib bazaga yozilgan
    bo'ladi. Olinmagan bo'lsa ID qaytadi — admin baribir suhbatni topadi.
    """
    if not enabled():
        return str(user_id)
    pool = await _conn()
    async with pool.acquire() as c:
        r = await c.fetchrow(
            "SELECT username, display_name FROM bot.contacts "
            " WHERE channel = 'instagram' AND user_id = $1",
            str(user_id),
        )
    if not r:
        return str(user_id)
    parts = [x for x in (r["display_name"], f"@{r['username']}" if r["username"] else "") if x]
    return " · ".join(parts) or str(user_id)


async def recent_messages(user_id: str, limit: int = 6) -> list[dict]:
    """Oxirgi xabarlar — signaldagi qisqa xulosa uchun."""
    if not enabled():
        return []
    pool = await _conn()
    async with pool.acquire() as c:
        rows = await c.fetch(
            "SELECT role, text FROM bot.messages "
            " WHERE channel = 'instagram' AND user_id = $1 AND text IS NOT NULL "
            " ORDER BY id DESC LIMIT $2",
            str(user_id), limit,
        )
    # `assistant` -> `model`: `report._summary` shu nomni kutadi.
    return [
        {"role": "user" if r["role"] == "user" else "model", "text": r["text"]}
        for r in reversed(rows)
    ]


# ─────────────────────────── Rejimni boshqarish ───────────────────────────
async def set_mode(user_id: str, mode: str) -> None:
    """«Javob beraman» / «AI davom ettirsin» tugmalari shu yerga tushadi.

    Instagram tomonida rejim ikkita ustunda: `human_takeover` (AI jim) va
    `pending_since` (boshqa admin javobi kutilyapti). Tugma bosilishi
    kutishni har ikki holatda ham yopadi — signal maqsadiga yetdi.
    """
    if not enabled():
        return
    pool = await _conn()
    async with pool.acquire() as c:
        if mode == "human":
            await c.execute(
                "UPDATE bot.conversations "
                "   SET human_takeover = TRUE, takeover_until = now() + ($2 || ' minutes')::interval, "
                "       pending_since = NULL, pending_notified = FALSE, updated_at = now() "
                " WHERE channel = 'instagram' AND user_id = $1",
                str(user_id), str(HUMAN_PAUSE_MINUTES),
            )
        else:  # ai
            await c.execute(
                "UPDATE bot.conversations "
                "   SET human_takeover = FALSE, takeover_until = NULL, "
                "       pending_since = NULL, pending_notified = TRUE, updated_at = now() "
                " WHERE channel = 'instagram' AND user_id = $1",
                str(user_id),
            )


async def set_ai_paused(paused: bool) -> None:
    """Kod 404 / 101 — Instagram kanalini butunlay to'xtatadi yoki yoqadi.

    Mavjud mexanizm ishlatiladi (`channel_policy.enabled`): o'chirilgan
    kanalda `guardrails.js` birinchi bosqichdayoq to'xtaydi, ya'ni AI
    umuman chaqirilmaydi va mijozga hech narsa yuborilmaydi.
    """
    if not enabled():
        return
    pool = await _conn()
    async with pool.acquire() as c:
        await c.execute(
            "UPDATE bot.channel_policy SET enabled = $1 WHERE channel = 'instagram'",
            not paused,
        )


async def is_ai_paused() -> bool:
    if not enabled():
        return False
    pool = await _conn()
    async with pool.acquire() as c:
        v = await c.fetchval(
            "SELECT enabled FROM bot.channel_policy WHERE channel = 'instagram'"
        )
    return v is False


# ─────────────────────── Kutish muddati tugaganlar ───────────────────────
async def expired_pending() -> list[str]:
    """30 daqiqa javob kelmagan Instagram suhbatlari.

    DIQQAT: bu yerda mijozga xabar YUBORILMAYDI. Instagram qoidasi —
    mijoz yozmaguncha ikkinchi xabar ketmaydi; xabar mijoz keyingi marta
    yozganda `guardrails.js` orqali beriladi. Bu ro'yxat faqat guruhdagi
    mavzuga belgi qo'yish uchun kerak emas — hozircha ishlatilmaydi,
    lekin holatni ko'rish uchun qoldirilgan.
    """
    if not enabled():
        return []
    cutoff = datetime.utcnow() - timedelta(minutes=WAIT_MINUTES)
    pool = await _conn()
    async with pool.acquire() as c:
        rows = await c.fetch(
            "SELECT user_id FROM bot.conversations "
            " WHERE channel = 'instagram' AND pending_since IS NOT NULL "
            "   AND pending_since <= $1",
            cutoff,
        )
    return [r["user_id"] for r in rows]
