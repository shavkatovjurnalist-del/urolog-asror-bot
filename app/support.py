"""Jonli operator guruhi — bemor bilan jonli admin o'rtasidagi ko'prik.

Muammo: Telegramda bir vaqtning o'zida bir necha bemor yozadi. Agar hamma
suhbat bitta oqimga tushsa, jonli admin kim nima yozganini ajrata olmaydi.
Instagramda bunday muammo yo'q — u yerda har suhbat allaqachon alohida.

Yechim: guruh **forum** rejimida (Mavzular / Topics yoqilgan) ishlaydi va
har bemarga bitta mavzu ochiladi. Suhbat — bemor xabarlari ham, AI javoblari
ham — o'sha mavzuda jonli ko'chib boradi. Admin mavzuga javob yozsa, xabar
bemorga ketadi va AI bir soatga jim bo'ladi.

Ishlash tartibi:
    bemor → bot → mavzu (👤 …)      AI javobi → bemor va mavzu (🤖 …)
    admin mavzuga yozdi → bemorga ketdi, `mode='human'`, AI pauzada
    bir soat o'tdi yoki admin `/ai` yozdi → AI qaytadi

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

from app.config import HUMAN_PAUSE_MINUTES, SUPPORT_GROUP_ID
from app.db import session_scope
from app.models import SupportThread

log = logging.getLogger(__name__)


def enabled() -> bool:
    return bool(SUPPORT_GROUP_ID)


def is_support_chat(chat_id: int) -> bool:
    return enabled() and chat_id == SUPPORT_GROUP_ID


# ─────────────────────────── Mavzu (topic) ───────────────────────────
def _title(user) -> str:
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
            th = SupportThread(tg_id=user.id, title=_title(user))
            s.add(th)
            await s.commit()
            await s.refresh(th)

        if th.topic_id:
            return th

        try:
            topic = await bot.create_forum_topic(
                chat_id=SUPPORT_GROUP_ID, name=_title(user)
            )
            th.topic_id = topic.message_thread_id
            th.title = _title(user)
            await s.commit()
            await s.refresh(th)
            await _send(
                bot,
                th,
                f"🆕 <b>Yangi suhbat</b>\n"
                f"👤 {escape(_title(user))} · <code>{user.id}</code>\n\n"
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


# ─────────────────────────── AI / odam rejimi ───────────────────────────
async def is_paused(tg_id: int) -> bool:
    """AI jim turishi kerakmi.

    Odam oxirgi javobidan `HUMAN_PAUSE_MINUTES` o'tmagan bo'lsa — ha.
    Vaqt o'tgach AI o'zi qaytadi (shifokorning qarori): admin unutib
    qo'ysa ham bemor javobsiz qolmaydi.
    """
    if not enabled():
        return False
    async with session_scope() as s:
        th = await get_thread(s, tg_id)
        if th is None or th.mode != "human":
            return False
        if th.human_at is None:
            return True
        if datetime.utcnow() - th.human_at < timedelta(minutes=HUMAN_PAUSE_MINUTES):
            return True
        # Pauza tugadi — AI ga qaytaramiz.
        th.mode = "ai"
        await s.commit()
        return False


async def set_mode(tg_id: int, mode: str) -> None:
    async with session_scope() as s:
        th = await get_thread(s, tg_id)
        if th is None:
            th = SupportThread(tg_id=tg_id)
            s.add(th)
        th.mode = mode
        if mode == "human":
            th.human_at = datetime.utcnow()
        await s.commit()
