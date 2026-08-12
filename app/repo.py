"""Bazadan kontent o'qish — bot va Mini App API uchun umumiy qatlam."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Advantage,
    Appointment,
    ChatMessage,
    Clinic,
    Consultation,
    Doctor,
    Faq,
    Method,
    Result,
    Service,
    User,
)


async def get_doctor(s: AsyncSession) -> Doctor | None:
    return (await s.execute(select(Doctor).limit(1))).scalar_one_or_none()


async def get_services(s: AsyncSession) -> list[Service]:
    q = select(Service).where(Service.is_active.is_(True)).order_by(Service.position)
    return list((await s.execute(q)).scalars())


async def get_service(s: AsyncSession, sid: int) -> Service | None:
    return await s.get(Service, sid)


async def get_methods(s: AsyncSession) -> list[Method]:
    return list((await s.execute(select(Method).order_by(Method.position))).scalars())


async def get_method(s: AsyncSession, mid: int) -> Method | None:
    return await s.get(Method, mid)


async def get_clinics(s: AsyncSession) -> list[Clinic]:
    return list((await s.execute(select(Clinic).order_by(Clinic.position))).scalars())


async def get_clinic(s: AsyncSession, cid: int) -> Clinic | None:
    return await s.get(Clinic, cid)


async def get_results(s: AsyncSession) -> list[Result]:
    return list((await s.execute(select(Result).order_by(Result.position))).scalars())


async def get_faq(s: AsyncSession) -> list[Faq]:
    return list((await s.execute(select(Faq).order_by(Faq.position))).scalars())


async def get_advantages(s: AsyncSession) -> list[Advantage]:
    return list((await s.execute(select(Advantage).order_by(Advantage.position))).scalars())


async def upsert_user(s: AsyncSession, tg_user, source: str = "bot") -> User:
    q = select(User).where(User.tg_id == tg_user.id)
    user = (await s.execute(q)).scalar_one_or_none()
    if user is None:
        user = User(tg_id=tg_user.id, source=source)
        s.add(user)
    user.username = getattr(tg_user, "username", "") or ""
    user.first_name = getattr(tg_user, "first_name", "") or ""
    user.last_name = getattr(tg_user, "last_name", "") or ""
    await s.commit()
    await s.refresh(user)
    return user


async def create_appointment(s: AsyncSession, **kwargs) -> Appointment:
    appt = Appointment(**kwargs)
    s.add(appt)
    await s.commit()
    await s.refresh(appt)
    return appt


async def create_consultation(s: AsyncSession, **kwargs) -> Consultation:
    c = Consultation(**kwargs)
    s.add(c)
    await s.commit()
    await s.refresh(c)
    return c


# ─────────────────────── «Jonli murojaat» suhbati ───────────────────────
async def add_chat_message(
    s: AsyncSession, tg_id: int, role: str, text: str,
    source: str = "bot", flags: str = "",
) -> ChatMessage:
    m = ChatMessage(tg_id=tg_id, role=role, text=text, source=source, flags=flags)
    s.add(m)
    await s.commit()
    return m


async def get_chat_history(s: AsyncSession, tg_id: int, limit: int = 14) -> list[dict]:
    """Modelga beriladigan suhbat tarixi — eng eskisi birinchi.

    Arxivlangan (yakunlangan) suhbatlar olinmaydi: yangi murojaat toza
    varaqdan boshlanadi.
    """
    q = (
        select(ChatMessage)
        .where(ChatMessage.tg_id == tg_id, ChatMessage.archived_at.is_(None))
        .order_by(ChatMessage.id.desc())
        .limit(limit)
    )
    rows = list((await s.execute(q)).scalars())
    return [{"role": m.role, "text": m.text} for m in reversed(rows)]


# ─────────────────────── Ish vaqtidagi sozlamalar ───────────────────────
# AI ni to'xtatish/qaytarish (kod 404 / 101). Kesh: har xabarda bazaga
# borilmasin, lekin to'xtatish 30 soniyadan ko'p kechikmasin.
_flag_cache: dict[str, tuple[float, str]] = {}
_FLAG_TTL = 30.0


async def get_setting(key: str, default: str = "") -> str:
    import time

    hit = _flag_cache.get(key)
    if hit and time.time() - hit[0] < _FLAG_TTL:
        return hit[1]
    from app.db import SessionLocal
    from app.models import Setting

    try:
        async with SessionLocal() as s:
            row = await s.get(Setting, key)
            val = row.value if row else default
    except Exception:  # baza yetib bo'lmasa bot ishlashda davom etsin
        return hit[1] if hit else default
    _flag_cache[key] = (time.time(), val)
    return val


async def set_setting(key: str, value: str) -> None:
    import time

    from app.db import SessionLocal
    from app.models import Setting

    async with SessionLocal() as s:
        row = await s.get(Setting, key)
        if row is None:
            s.add(Setting(key=key, value=value))
        else:
            row.value = value
        await s.commit()
    _flag_cache[key] = (time.time(), value)


async def ai_paused() -> bool:
    return (await get_setting("ai_paused", "false")) == "true"


async def has_open_chat(s: AsyncSession, tg_id: int) -> bool:
    """Yakunlanmagan jonli suhbat bormi.

    Kerak: bot qayta ishga tushganda FSM holati (MemoryStorage) yo'qoladi,
    lekin bemor uchun suhbat davom etayotgan bo'ladi. Shu bayroq bo'yicha
    holat tiklanadi — bemor «Menyudan tanlang» degan javob olmaydi.
    """
    q = (
        select(ChatMessage.id)
        .where(ChatMessage.tg_id == tg_id, ChatMessage.archived_at.is_(None))
        .limit(1)
    )
    return (await s.execute(q)).scalar_one_or_none() is not None


async def archive_chat_history(s: AsyncSession, tg_id: int) -> int:
    """Suhbatni yopadi: qatorlar o'chirilmaydi, `archived_at` to'ldiriladi.

    Nima uchun o'chirilmaydi: haqiqiy suhbatlar AI ni o'qitishning asosiy
    manbai. Ularni ko'rish: `python -m scripts.export_chats`.
    """
    res = await s.execute(
        update(ChatMessage)
        .where(ChatMessage.tg_id == tg_id, ChatMessage.archived_at.is_(None))
        .values(archived_at=datetime.utcnow())
    )
    await s.commit()
    return res.rowcount or 0
