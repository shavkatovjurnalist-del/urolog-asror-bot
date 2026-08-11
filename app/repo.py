"""Bazadan kontent o'qish — bot va Mini App API uchun umumiy qatlam."""
from __future__ import annotations

from sqlalchemy import delete, select
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
    """Modelga beriladigan suhbat tarixi — eng eskisi birinchi."""
    q = (
        select(ChatMessage)
        .where(ChatMessage.tg_id == tg_id)
        .order_by(ChatMessage.id.desc())
        .limit(limit)
    )
    rows = list((await s.execute(q)).scalars())
    return [{"role": m.role, "text": m.text} for m in reversed(rows)]


async def clear_chat_history(s: AsyncSession, tg_id: int) -> None:
    """Suhbat yakunlanganda tarix tozalanadi — keyingi murojaat toza boshlanadi."""
    await s.execute(delete(ChatMessage).where(ChatMessage.tg_id == tg_id))
    await s.commit()
