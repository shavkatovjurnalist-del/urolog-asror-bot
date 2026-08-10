"""Tez tekshiruv: klaviatura va matnlar xatosiz yig'ilyaptimi."""
from __future__ import annotations

import asyncio

from app import repo
from app.bot import keyboards as kb
from app.bot import texts as t
from app.db import SessionLocal, init_db


async def main() -> None:
    await init_db()
    async with SessionLocal() as s:
        doctor = await repo.get_doctor(s)
        services = await repo.get_services(s)
        methods = await repo.get_methods(s)
        clinics = await repo.get_clinics(s)
        faq = await repo.get_faq(s)
        advantages = await repo.get_advantages(s)

    print("webapp tugmalari yoqilgan:", kb.WEBAPP_ENABLED)
    print("main_menu qatorlari:", len(kb.main_menu().keyboard))
    print("xizmatlar ro'yxati:", len(kb.list_kb(services, "svc").inline_keyboard))
    print("usullar ro'yxati:", len(kb.list_kb(methods, "mtd").inline_keyboard))
    print("aloqa tugmalari:", len(kb.contact_kb(doctor).inline_keyboard))
    print("klinika tugmalari:", len(kb.clinic_kb(clinics[0]).inline_keyboard))
    print("detail tugmalari:", len(kb.detail_kb("svc:list").inline_keyboard))

    for name, text in [
        ("welcome", t.welcome(doctor)),
        ("doctor", t.doctor_card(doctor)),
        ("service", t.service_card(services[0])),
        ("method", t.method_card(methods[0])),
        ("clinic", t.clinic_card(clinics[0])),
        ("faq", t.faq_text(faq)),
        ("advantages", t.advantages_text(advantages)),
        ("contact", t.contact_text(doctor)),
    ]:
        assert text and len(text) < 4096, f"{name}: uzunlik {len(text)}"
        print(f"{name}: {len(text)} belgi ✅")

    print("\n✅ Hammasi joyida.")


if __name__ == "__main__":
    asyncio.run(main())
