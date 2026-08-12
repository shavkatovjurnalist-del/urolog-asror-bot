"""Operator guruhi — bemor bilan boshqa admin o'rtasidagi ko'prik.

Muammo: Telegramda bir vaqtning o'zida bir necha bemor yozadi. Agar hamma
suhbat bitta oqimga tushsa, admin kim nima yozganini ajrata olmaydi.
Instagramda bunday muammo yo'q — u yerda har suhbat allaqachon alohida.

Yechim: guruh **forum** rejimida (Mavzular / Topics yoqilgan) ishlaydi va
har bemarga bitta mavzu ochiladi. Suhbat — bemor xabarlari ham, AI javoblari
ham — o'sha mavzuda jonli ko'chib boradi. Admin mavzuga javob yozsa, xabar
bemorga ketadi va AI bir soatga jim bo'ladi.

Guruhga HAMMA yozishma tushadi, signal esa (`report.escalation`) faqat
odam kerak bo'lgan holatlarda ketadi — ikkalasi alohida narsa.

Ishlash tartibi:
    bemor → bot → mavzu (👤 …)      AI javobi → bemor va mavzu (🤖 …)
    bemor odam so'radi → `waiting`, signal + tugmalar, AI jim
    admin «Javob beraman» yoki mavzuga yozdi → `human`, AI 60 daqiqa jim
    admin «AI davom ettirsin» yoki 30 daqiqa jim → `ai` ga qaytadi

Guruh sozlanmagan bo'lsa (`SUPPORT_GROUP_ID=0`) modul butunlay jim turadi va
bot avvalgidek ishlayveradi — bu qasddan: guruh ochilmaguncha hech narsa
buzilmasin.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from html import escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import HUMAN_PAUSE_MINUTES, SUPPORT_GROUP_ID, WAIT_MINUTES
from app.db import session_scope
from app.models import SupportThread

log = logging.getLogger(__name__)


def enabled() -> bool:
    return bool(SUPPORT_GROUP_ID)


def is_support_chat(chat_id: int) -> bool:
    return enabled() and chat_id == SUPPORT_GROUP_ID


# ─────────────────────────── Mavzu (topic) ───────────────────────────
def title_of(user) -> str:
    """Mavzu sarlavhasi: admin bemorni ro'yxatdan tanishi uchun."""
    name = " ".join(
        x for x in (getattr(user, "first_name", ""), getattr(user, "last_name", "")) if x
    ).strip()
    uname = getattr(user, "username", "")
    parts = [name or f"id{user.id}"]
    if uname:
        parts.append(f"@{uname}")
    return " · ".join(parts)[:128]


async def get_thread(s: AsyncSession, tg_id: int) -> SupportThread | None:
    q = select(SupportThread).where(SupportThread.tg_id == tg_id)
    return (await s.execute(q)).scalar_one_or_none()


async def ensure_thread(bot, user) -> SupportThread | None:
    """Bemorning mavzusini topadi yoki yangisini ochadi.

    Guruh forum emas yoki botda huquq yo'q bo'lsa — `topic_id` bo'sh qoladi
    va xabarlar guruhning umumiy oqimiga tushadi. Bu ideal emas, lekin
    xabarlar yo'qolib ketgandan ko'ra yaxshi.
    """
    if not enabled():
        return None

    async with session_scope() as s:
        th = await get_thread(s, user.id)
        if th is None:
            th = SupportThread(tg_id=user.id, title=title_of(user))
            s.add(th)
            await s.commit()
            await s.refresh(th)

        if th.topic_id:
            return th

        try:
            topic = await bot.create_forum_topic(
                chat_id=SUPPORT_GROUP_ID, name=title_of(user)
            )
            th.topic_id = topic.message_thread_id
            th.title = title_of(user)
            await s.commit()
            await s.refresh(th)
            await _send(
                bot,
                th,
                f"🆕 <b>Yangi suhbat</b>\n"
                f"👤 {escape(title_of(user))} · <code>{user.id}</code>\n\n"
                f"Bu mavzuga yozgan xabaringiz to'g'ridan-to'g'ri bemorga ketadi "
                f"va AI bir soatga jim bo'ladi.\n"
                f"AI ni darhol qaytarish uchun: /ai",
            )
        except Exception as e:
            # Guruh forum emas yoki bot admin emas. Ishni to'xtatmaymiz.
            log.warning("Mavzu ochilmadi (%s): %s", user.id, e)
        return th


async def thread_by_topic(s: AsyncSession, topic_id: int) -> SupportThread | None:
    q = select(SupportThread).where(SupportThread.topic_id == topic_id)
    return (await s.execute(q)).scalar_one_or_none()


# ─────────────────────────── Yuborish ───────────────────────────
async def _send(bot, th: SupportThread | None, text: str) -> None:
    if not enabled():
        return
    kwargs = {"chat_id": SUPPORT_GROUP_ID, "text": text, "parse_mode": "HTML"}
    if th and th.topic_id:
        kwargs["message_thread_id"] = th.topic_id
    try:
        await bot.send_message(**kwargs)
    except Exception as e:
        # Mavzu o'chirilgan bo'lishi mumkin — keyingi safar qayta ochiladi.
        log.warning("Guruhga yuborilmadi: %s", e)
        if th and th.topic_id:
            async with session_scope() as s:
                obj = await s.get(SupportThread, th.id)
                if obj:
                    obj.topic_id = None
                    await s.commit()
            kwargs.pop("message_thread_id", None)
            try:
                await bot.send_message(**kwargs)
            except Exception as e2:
                log.warning("Guruhga umumiy oqimga ham yuborilmadi: %s", e2)


async def relay_user_text(bot, user, text: str, note: str = "") -> None:
    """Bemor yozgan matnni mavzuga ko'chiradi."""
    if not enabled():
        return
    th = await ensure_thread(bot, user)
    body = f"👤 {escape(text)}"
    if note:
        body = f"👤 <i>{escape(note)}</i>\n{escape(text)}"
    await _send(bot, th, body)


async def relay_user_media(bot, user, message, note: str) -> None:
    """Bemor yuborgan rasm/ovozni ASL HOLICHA mavzuga ko'chiradi.

    `copy_message` ishlatiladi: admin faylni o'zini ko'radi va eshitadi.
    Ilgari guruhga faqat «rasm keldi» degan quruq matn tushardi.
    """
    if not enabled():
        return
    th = await ensure_thread(bot, user)
    await _send(bot, th, f"👤 <i>{escape(note)}</i>")
    try:
        kwargs = {
            "chat_id": SUPPORT_GROUP_ID,
            "from_chat_id": message.chat.id,
            "message_id": message.message_id,
        }
        if th and th.topic_id:
            kwargs["message_thread_id"] = th.topic_id
        await bot.copy_message(**kwargs)
    except Exception as e:
        log.warning("Media ko'chirilmadi (%s): %s", user.id, e)


async def relay_ai(bot, tg_id: int, text: str) -> None:
    """AI javobini mavzuga ko'chiradi — admin suhbatni jonli kuzatadi."""
    if not enabled():
        return
    async with session_scope() as s:
        th = await get_thread(s, tg_id)
    if th is None:
        return
    await _send(bot, th, f"🤖 {escape(text)}")


async def notify(bot, tg_id: int, text: str) -> None:
    """Diqqat talab qiladigan holat haqida mavzuga xizmat xabari."""
    if not enabled():
        return
    async with session_scope() as s:
        th = await get_thread(s, tg_id)
    await _send(bot, th, text)


# ─────────────────────── Mavzuga havola ───────────────────────
def topic_link(topic_id: int | None) -> str:
    """Guruhdagi mavzuni ochadigan havola.

    Yopiq supergruppa uchun manzil `t.me/c/<id>/<mavzu>` ko'rinishida
    bo'ladi — `-100` prefiksi olib tashlanadi. Admin signalni bosib
    to'g'ridan-to'g'ri o'sha bemorning suhbatiga tushadi.
    """
    if not enabled():
        return ""
    raw = str(SUPPORT_GROUP_ID)
    short = raw[4:] if raw.startswith("-100") else raw.lstrip("-")
    return f"https://t.me/c/{short}/{topic_id}" if topic_id else f"https://t.me/c/{short}"


# ─────────────────────────── AI / odam rejimi ───────────────────────────
async def is_paused(tg_id: int) -> bool:
    """AI jim turishi kerakmi.

    Ikki sabab bo'lishi mumkin:
      • `human`  — admin javob berdi, `HUMAN_PAUSE_MINUTES` jim turamiz;
      • `waiting` — boshqa adminga signal ketdi, `WAIT_MINUTES` javob kutamiz.

    Ikkala muddat ham shu yerda tekshiriladi va o'zi tugaydi. Buni jadvalga
    (`support.watch_pending`) tashlab qo'ymaslik kerak: servis uxlab qolsa
    jadval ishlamaydi va bemor abadiy javobsiz qolardi.
    """
    if not enabled():
        return False
    async with session_scope() as s:
        th = await get_thread(s, tg_id)
        if th is None or th.mode not in ("human", "waiting"):
            return False

        if th.mode == "human":
            if th.human_at is None:
                return True
            if datetime.utcnow() - th.human_at < timedelta(minutes=HUMAN_PAUSE_MINUTES):
                return True
        else:  # waiting
            if th.pending_since is None:
                return True
            if datetime.utcnow() - th.pending_since < timedelta(minutes=WAIT_MINUTES):
                return True

        # Muddat tugadi — AI ga qaytaramiz.
        th.mode = "ai"
        await s.commit()
        return False


async def set_mode(tg_id: int, mode: str) -> None:
    """Rejimni almashtiradi va tegishli vaqt belgisini qo'yadi."""
    async with session_scope() as s:
        th = await get_thread(s, tg_id)
        if th is None:
            th = SupportThread(tg_id=tg_id)
            s.add(th)
        th.mode = mode
        if mode == "human":
            th.human_at = datetime.utcnow()
            # Admin javob berdi — kutish tugadi.
            th.pending_since = None
            th.pending_notified = False
        elif mode == "waiting":
            th.pending_since = datetime.utcnow()
            th.pending_notified = False
        else:  # ai
            th.pending_since = None
            th.pending_notified = False
        await s.commit()


async def expired_pending() -> list[int]:
    """Javob kutib muddati o'tgan bemorlar — har biriga bir marta qaytariladi.

    Chaqirilishi bilan `pending_notified` qo'yiladi, shuning uchun bir bemorga
    ikkinchi marta xabar ketmaydi.
    """
    if not enabled():
        return []
    cutoff = datetime.utcnow() - timedelta(minutes=WAIT_MINUTES)
    async with session_scope() as s:
        q = select(SupportThread).where(
            SupportThread.mode == "waiting",
            SupportThread.pending_notified.is_(False),
            SupportThread.pending_since.is_not(None),
            SupportThread.pending_since <= cutoff,
        )
        rows = list((await s.execute(q)).scalars())
        for th in rows:
            th.pending_notified = True
            th.mode = "ai"
            th.pending_since = None
        if rows:
            await s.commit()
    return [th.tg_id for th in rows]


async def pending_watcher(bot) -> None:
    """Javob kutish muddati tugaganlarga xabar beradi (Telegram uchun).

    Shifokorning qarori: admin signalni e'tiborsiz qoldirsa ham bemor
    javobsiz qolmasin — unga xabar berilib, suhbat AI bilan davom etadi.
    """
    import asyncio

    from app import persona, repo

    while True:
        await asyncio.sleep(120)
        try:
            for tg_id in await expired_pending():
                try:
                    await bot.send_message(tg_id, persona.HANDOFF_TIMEOUT)
                except Exception as e:
                    log.warning("Kutish xabari ketmadi (%s): %s", tg_id, e)
                    continue
                async with session_scope() as s:
                    await repo.add_chat_message(
                        s, tg_id, "model", persona.HANDOFF_TIMEOUT, flags="kutish_tugadi"
                    )
                await notify(
                    bot, tg_id,
                    "⏳ <b>Javob kelmadi</b> — bemorga xabar berildi, AI davom etadi.",
                )
        except Exception as e:
            log.warning("Kutish nazoratchisi xatosi: %s", e)
