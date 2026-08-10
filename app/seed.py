"""Sayt (urologasrorturayev.uz) kontentini bazaga yuklash.

Matnlar saytdan olingan. Kontentni o'zgartirish kerak bo'lsa — shu faylni
tahrirlab `python -m app.seed` ni qayta ishga tushirish kifoya (upsert qiladi).
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models import Advantage, Clinic, Doctor, Faq, Method, Result, Service

DOCTOR = dict(
    full_name="To'rayev Asror Abbosovich",
    short_name="Dr. Asror To'rayev",
    specialty="Urolog-Androlog",
    category="Oliy toifali shifokor",
    experience="5+ yil",
    bio=(
        "Men urolog-androlog shifokorman. Samarqand shahrida faoliyat yuritaman va "
        "bemorlarimga zamonaviy tibbiyot yutuqlaridan foydalangan holda yordam beraman.\n\n"
        "Asosiy yo'nalishlarim: jinsiy olatga protez o'rnatish, prostata adenomasi va "
        "buyrak toshlarini lazerda olish, bepushtlikning barcha turlari, varikosele, "
        "gidrosele, kistalar, denervatsiya, TESE / Micro-TESE, jinsiy zaiflik va tez "
        "bo'shanishning barcha turlarini davolash."
    ),
    photo="/app/assets/asror.webp",
    phone="+998 90 008 38 78",
    email="dr.torayev@medical.uz",
    telegram="https://t.me/urolog_asrorturayev",
    instagram="https://www.instagram.com/urolog_asrorturayev/",
    youtube="https://youtube.com/@samarqand_urolog",
    website="https://urologasrorturayev.uz",
    work_hours="Dushanbadan Shanbagacha, 09:00 – 19:00",
)

SERVICES = [
    dict(
        slug="penil-protez",
        icon="🔧",
        title="Penil protez (jinsiy olatga protez)",
        short="Erektil disfunksiyani davolashning yakuniy va eng samarali usuli",
        description=(
            "Erektil disfunksiya — potensiya yo'qolishini davolashning eng samarali yakuniy usuli. "
            "Jinsiy olatga maxsus protez o'rnatiladi: tabiiy ko'rinish va to'liq jinsiy faoliyat "
            "tiklanadi. Operatsiya xavfsiz va yuqori, barqaror natija beradi."
        ),
    ),
    dict(
        slug="moyak-operatsiyalari",
        icon="🩹",
        title="Moyakdagi operatsiyalar — endi chandiqsiz",
        short="Rafe liniyasidan kesma — chandiq ko'rinmaydi",
        description=(
            "Operatsion kesma rafe liniyasidan — ikkita moyak o'rtasidan o'tgan tabiiy chiziqdan "
            "amalga oshiriladi, shu sababli chandiq ko'rinmaydi. Gidrosele, moyak ortig'i kistalari, "
            "TESE/MicroTESE, spermatosele va moyak hosilalari shu usulda davolanadi."
        ),
    ),
    dict(
        slug="prostata",
        icon="🔬",
        title="Prostataga oid operatsiyalar",
        short="HoLEP, TUR va prostatektomiya — kesmasiz",
        description=(
            "Zamonaviy adenoma va prostata saratonini davolash: HoLEP, TUR va prostatektomiya. "
            "Kesmalarsiz, tez tiklanish va funksiyalarni saqlab qolgan holda."
        ),
    ),
    dict(
        slug="ayollarda-siydik-tutolmaslik",
        icon="👩",
        title="Ayollarda siydik tutolmasligi operatsiyalari",
        short="TVT/TOT slinglari yordamida davolash",
        description=(
            "Stressli siydik tutolmasligini TVT/TOT slinglari yordamida davolash. "
            "Tez, samarali va ayol salomatligiga e'tibor bilan."
        ),
    ),
    dict(
        slug="siydik-pufagi",
        icon="💧",
        title="Siydik pufagiga oid operatsiyalar",
        short="O'smalar, toshlar va pufakni tiklash",
        description=(
            "O'smalar, toshlar va siydik pufagini tiklash. Kesiksiz va Samarqandda "
            "minimal reabilitatsiya bilan."
        ),
    ),
    dict(
        slug="siydik-naychasi",
        icon="🧵",
        title="Siydik naychasidagi operatsiyalar",
        short="Toshlar, torayish va shikastlanishlar",
        description=(
            "Toshlarni olib tashlash, torayish va shikastlanishlarda siydik naychasi plastikasi "
            "va ko'chirish. Organik funksiyalarni saqlab qolgan holda yumshoq usullar orqali davolash."
        ),
    ),
    dict(
        slug="buyrak",
        icon="🫘",
        title="Buyrak operatsiyalari",
        short="Lazer, laparoskopiya va PCNL",
        description=(
            "Lazer yordamida toshlarni olib tashlash, rezeksiya va nefrektomiya. "
            "Murakkab buyrak kasalliklarini laparoskopiya va PCNL usuli orqali davolash."
        ),
    ),
    dict(
        slug="moyak-va-ortigi",
        icon="⚕️",
        title="Moyak va moyak ortig'i operatsiyalari",
        short="Varikotsele, gidrotsele, o'smalar, kriptorxizm",
        description=(
            "Varikotsele, gidrotsele (suv yig'ilishi), o'smalar, burilish va kriptorxizm. "
            "Erkaklar salomatligi uchun nozik va xavfsiz davolash."
        ),
    ),
    dict(
        slug="uretra-jarrohligi",
        icon="✂️",
        title="Uretra va jinsiy a'zolar jarrohligi",
        short="Uretra plastikasi, sunnat, frenulotomiya",
        description=(
            "Uretra plastikasi, sunnat qilish, frenulotomiya va egri shaklni to'g'rilash. "
            "Har bir bemorga individual yondashuv bilan ishonch va qulaylik."
        ),
    ),
    dict(
        slug="bepushtlik",
        icon="👶",
        title="Bepushtlikning barcha turlari",
        short="Andrologik tekshiruv, TESE / Micro-TESE",
        description=(
            "Erkaklar bepushtligining barcha turlarini tekshirish va davolash. Spermogramma va "
            "gormonal tekshiruvlar asosida individual davolash rejasi tuziladi. Zarur hollarda "
            "mikroskop ostida moyakdan sperm hujayralarini olish (TESE / Micro-TESE) hamda "
            "varikotsele va vazovazostomiya operatsiyalari bajariladi."
        ),
    ),
    dict(
        slug="jinsiy-zaiflik",
        icon="💪",
        title="Jinsiy zaiflik va tez bo'shanish",
        short="Konservativ va operativ davolash, denervatsiya",
        description=(
            "Jinsiy zaiflik va tez bo'shanishning barcha turlarini davolash. Konservativ davolash "
            "natija bermagan hollarda denervatsiya va ligamentotomiya kabi operativ usullar "
            "qo'llaniladi. Har bir holat alohida ko'rib chiqiladi."
        ),
    ),
]

METHODS = [
    dict(
        slug="tur",
        icon="🔁",
        title="TUR (Transuretral rezeksiya)",
        description=(
            "Siydik yo'li orqali kesimsiz bajariladigan operatsiya. Prostata adenomasi, "
            "siydik pufagi o'smalari va torayishlarni davolashda qo'llaniladi."
        ),
    ),
    dict(
        slug="holep",
        icon="🔆",
        title="HoLEP (Holmium lazer enukleatsiya)",
        description=(
            "Prostata adenomasini lazer yordamida olib tashlash. Qon ketishi minimal, "
            "kateter tez olinadi va kasalxonada yotish qisqa."
        ),
    ),
    dict(
        slug="pcnl",
        icon="🎯",
        title="PCNL (Perkutan nefrolitotomiya)",
        description=(
            "Bel terisidan kichik teshik orqali buyrak toshlarini maydalab olib tashlash. "
            "2 sm dan katta toshlar uchun eng samarali usul."
        ),
    ),
    dict(
        slug="urs",
        icon="🔎",
        title="URS (Ureteroskopiya)",
        description=(
            "Siydik naycha orqali endoskop kiritib, ureter va buyrak toshlarini lazer bilan "
            "maydalab olib tashlash. Kesimsiz va tez tiklanish bilan."
        ),
    ),
    dict(
        slug="laparoskopiya",
        icon="📹",
        title="Laparoskopik jarrohlik",
        description=(
            "Qorin bo'shlig'iga 3-4 ta kichik teshik orqali kamera va asboblar kiritib "
            "bajariladigan operatsiya. Buyrak, ureter va prostata operatsiyalarida qo'llaniladi."
        ),
    ),
    dict(
        slug="mikroxirurgiya",
        icon="🔬",
        title="Mikroxirurgiya (TESE / Micro-TESE)",
        description=(
            "Mikroskop ostida moyakdan sperm hujayralarini olish. Bepushtlikni davolashda, "
            "varikotsele va vazovazostomiya operatsiyalarida qo'llaniladi."
        ),
    ),
]

ADVANTAGES = [
    dict(icon="🏅", title="Oliy toifali mutaxassis",
         description="Oliy toifali urolog-androlog sifatida murakkab operatsiyalarni muvaffaqiyatli bajaraman."),
    dict(icon="⚙️", title="Zamonaviy texnologiyalar",
         description="HoLEP, laparoskopiya, PCNL va boshqa ilg'or usullar bilan kesimsiz davolayman."),
    dict(icon="🪶", title="Minimal invaziv yondashuv",
         description="Og'riqsiz, qon ketishi kam va tez tiklanish — bemorlar hayot sifatini saqlab qolaman."),
    dict(icon="🤝", title="Individual yondashuv",
         description="Har bir bemorga alohida e'tibor va uning holatiga mos davolash rejasini tuzaman."),
    dict(icon="⚡", title="Tez tiklanish",
         description="Zamonaviy usullar tufayli kasalxonada yotish qisqa va kundalik hayotga tez qaytish."),
    dict(icon="💬", title="Doimiy aloqa",
         description="Operatsiyadan oldin va keyin to'liq maslahat va kuzatuv. Telegram orqali doim aloqadaman."),
]

CLINICS = [
    dict(
        name="Sintez Lab Klinikasi",
        address="Samarqand shahar, Laxuti ko'chasi, 2A",
        landmark="Mo'ljal: 6-hammom, Brilliant City",
        map_url="https://yandex.uz/maps/-/CTAduM2O",
        latitude=39.654, longitude=66.959,
        photo="/app/assets/clinic3.webp",
        work_hours="Dush–Shan, 09:00 – 19:00",
    ),
    dict(
        name="Med Fast Clinic",
        address="Samarqand shahar, Ozod Sharq ko'chasi, 8-uy",
        landmark="",
        map_url="https://yandex.uz/maps/?text=Samarqand+Ozod+Sharq+ko'chasi+8",
        latitude=39.665, longitude=66.975,
        photo="/app/assets/clinic4.webp",
        work_hours="Dush–Shan, 09:00 – 19:00",
    ),
]

# Videolar @samarqand_urolog kanalidan olingan (saytdagi eski ID'lar o'chib ketgan).
RESULTS = [
    dict(title="Farzandsizlik muammosi", youtube_id="BYXxrmaTiBw"),
    dict(title="Tez-tez siyishga borish", youtube_id="Na9GAsYnr6E"),
    dict(title="Jinsiy muammolar kelib chiqishi", youtube_id="AUKwUevomCo"),
    dict(title="Siydik yo'li achishishi muammosi", youtube_id="la-USx62sIU"),
    dict(title="Moyakka og'riq beruvchi omillar", youtube_id="eSIC8XZvsv4"),
    dict(title="Moyaklar o'lchamining kattalashishi", youtube_id="NXGybhsS1aU"),
    dict(title="Ginekomastiya — erkaklarda ko'krak kattalashishi", youtube_id="oycrgM0bDTk"),
    dict(title="Siydik yo'lidan tosh oldirganda", youtube_id="mi-frE4M3xk"),
    dict(title="Yoshi katta insonlarda jinsiy muammolar", youtube_id="hYrdAutAfXA"),
    dict(title="Kattalarda prostata adenomasi va qovuq toshi", youtube_id="IMqfGNToklc"),
    dict(title="Ushbu holatlar kuzatilsa…", youtube_id="vhyupEPxKNo"),
    dict(title="Operatsiya jarayoni", youtube_id="06netuUihNQ"),
]

FAQ = [
    dict(question="Qabulga qanday yozilaman?",
         answer="Bot orqali «Qabulga yozilish» tugmasini bosing, ism va telefon raqamingizni "
                "qoldiring — shifokor jamoasi siz bilan bog'lanadi. Yoki to'g'ridan-to'g'ri "
                "+998 90 008 38 78 raqamiga qo'ng'iroq qilishingiz mumkin."),
    dict(question="Qabul kunlari va vaqti qanday?",
         answer="Dushanbadan Shanbagacha, soat 09:00 dan 19:00 gacha. Qabul oldindan yozilish asosida."),
    dict(question="Qayerda qabul qilasiz?",
         answer="Samarqand shahrida ikkita klinikada: Sintez Lab Klinikasi (Laxuti ko'chasi, 2A) va "
                "Med Fast Clinic (Ozod Sharq ko'chasi, 8-uy)."),
    dict(question="HoLEP nima va oddiy operatsiyadan farqi nimada?",
         answer="HoLEP — prostata adenomasini holmium lazer yordamida olib tashlash usuli. "
                "Kesma qilinmaydi, qon ketishi minimal, kateter tezroq olinadi va kasalxonada "
                "yotish muddati qisqaradi."),
    dict(question="Operatsiyadan keyin qancha vaqtda tiklanaman?",
         answer="Minimal invaziv usullardan keyin ko'pchilik bemorlar bir necha kun ichida "
                "kundalik hayotga qaytadi. Aniq muddat operatsiya turi va sog'liq holatiga bog'liq — "
                "buni shifokor ko'rikdan so'ng aytadi."),
    dict(question="Bepushtlik davolanadimi?",
         answer="Ha. Erkaklar bepushtligining barcha turlari bo'yicha tekshiruv va davolash olib "
                "boriladi, jumladan TESE / Micro-TESE va varikotsele operatsiyalari. "
                "Avval spermogramma va gormonal tekshiruvlar talab qilinadi."),
    dict(question="Ayollarni qabul qilasizmi?",
         answer="Ha, ayollarda siydik tutolmasligi (TVT/TOT slinglari), siydik pufagi va buyrak "
                "kasalliklari bo'yicha jarrohlik yordami ko'rsatiladi."),
    dict(question="Onlayn maslahat olsam bo'ladimi?",
         answer="Ha, Telegram orqali savolingizni yozib qoldirishingiz mumkin. Lekin aniq tashxis "
                "uchun bevosita ko'rik va tekshiruvlar zarur."),
    dict(question="Narxlar qanday?",
         answer="Narx tashxis, operatsiya turi va klinikaga bog'liq holda belgilanadi. Aniq narxni "
                "bilish uchun qabulga yoziling yoki +998 90 008 38 78 raqamiga qo'ng'iroq qiling."),
]


async def _upsert(session, model, rows, key, prune: bool = False):
    """Kontentni yangilaydi. `prune=True` bo'lsa ro'yxatda yo'q yozuvlarni o'chiradi.

    Prune faqat boshqa jadvallar bog'lanmagan modellar uchun ishlatiladi
    (Service va Clinic ga arizalar bog'langani uchun ular o'chirilmaydi).
    """
    keys = {row[key] for row in rows}
    for i, row in enumerate(rows):
        data = {**row, "position": i}
        stmt = select(model).where(getattr(model, key) == row[key])
        obj = (await session.execute(stmt)).scalar_one_or_none()
        if obj:
            for k, v in data.items():
                setattr(obj, k, v)
        else:
            session.add(model(**data))

    if prune:
        for obj in (await session.execute(select(model))).scalars():
            if getattr(obj, key) not in keys:
                await session.delete(obj)


async def seed() -> None:
    await init_db()
    async with SessionLocal() as session:
        doc = (await session.execute(select(Doctor))).scalar_one_or_none()
        if doc:
            for k, v in DOCTOR.items():
                setattr(doc, k, v)
        else:
            session.add(Doctor(**DOCTOR))

        await _upsert(session, Service, SERVICES, "slug")
        await _upsert(session, Clinic, CLINICS, "name")
        await _upsert(session, Method, METHODS, "slug", prune=True)
        await _upsert(session, Advantage, ADVANTAGES, "title", prune=True)
        await _upsert(session, Result, RESULTS, "youtube_id", prune=True)
        await _upsert(session, Faq, FAQ, "question", prune=True)

        await session.commit()
    print("✅ Kontent bazaga yuklandi.")


if __name__ == "__main__":
    asyncio.run(seed())
