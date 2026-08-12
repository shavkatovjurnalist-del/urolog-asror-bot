"""AI-konsultant — Google Gemini.

Uch qism:
  • `app/knowledge.py` — anketadan olingan faktlar;
  • `app/persona.py`   — kim va qanday gapiradi;
  • bu fayl           — modelga so'rov va javobni tozalash.

Bilim bazasi ikkita manbadan yig'iladi (`build_context`):
  1) bazadagi kontent — xizmatlar, usullar, FAQ, klinika, shifokor profili
     (bot va Mini App ko'rsatadigan ma'lumotning aynan o'zi);
  2) shifokor anketasining aniqlashtiruvchi javoblari.

Kontekst 10 daqiqaga keshlanadi — har xabarda bazani qayta o'qish shart emas.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time

import httpx

from app import repo, persona
from app.config import AI_API_KEY, AI_ENABLED, AI_MODEL
from app.db import SessionLocal
from app.knowledge import knowledge_text

log = logging.getLogger(__name__)

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Suhbat xotirasi: modelga beriladigan oxirgi xabarlar soni (juftlik emas, dona).
HISTORY_LIMIT = 14

_ctx_cache: tuple[float, str] | None = None
_CTX_TTL = 600  # soniya


# ─────────────────────────── Bilim bazasi ───────────────────────────
async def build_context(force: bool = False) -> str:
    """Bazadagi kontent + anketa faktlari. 10 daqiqaga keshlanadi."""
    global _ctx_cache
    if not force and _ctx_cache and time.time() - _ctx_cache[0] < _CTX_TTL:
        return _ctx_cache[1]

    parts: list[str] = []
    try:
        async with SessionLocal() as s:
            doctor = await repo.get_doctor(s)
            services = await repo.get_services(s)
            methods = await repo.get_methods(s)
            clinics = await repo.get_clinics(s)
            faq = await repo.get_faq(s)

        if clinics:
            parts.append(
                "QABUL JOYLARI (bazadan):\n"
                + "\n".join(
                    f"- {c.name}, {c.address}"
                    + (f" ({c.landmark})" if c.landmark else "")
                    for c in clinics
                )
            )
        if services:
            parts.append(
                "XIZMATLAR (bot va Mini App ko'rsatadigan tavsiflar):\n"
                + "\n".join(f"- {x.title}: {x.description}" for x in services)
            )
        if methods:
            parts.append(
                "JARROHLIK USULLARI:\n"
                + "\n".join(f"- {x.title}: {x.description}" for x in methods)
            )
        if faq:
            parts.append(
                "KO'P BERILADIGAN SAVOLLAR:\n"
                + "\n".join(f"S: {x.question}\nJ: {x.answer}" for x in faq)
            )
        if doctor:
            parts.append(f"SHIFOKOR HAQIDA (saytdan):\n{doctor.bio}")
    except Exception as e:  # baza yetib bo'lmasa ham AI ishlashi kerak
        log.warning("Kontekstni bazadan olishda xato: %s", e)

    # Anketa javoblari — eng ishonchli manba, oxirida turadi.
    parts.append("SHIFOKORNING ANIQLASHTIRUVCHI JAVOBLARI (anketa):\n" + knowledge_text())

    ctx = "\n\n".join(parts)
    _ctx_cache = (time.time(), ctx)
    return ctx


# ─────────────────────────── Javobni tozalash ───────────────────────────
# Model qoidani buzsa — mijozga ketishidan oldin to'xtatiladi.
# Narx filtri OLIB TASHLANDI (2026-08-11): shifokor narxlarni aytishga ruxsat
# berdi, ular endi `knowledge.PRICE_FACTS` da. Filtr faqat eski klinika nomini
# to'sadi.
_MEDFAST_RE = re.compile(r"med\s*fast|ozod\s*sharq", re.IGNORECASE)

# Narx RO'YXATI — alohida to'siq (2026-08-11, shifokorning talabi).
# Muammo: «hamma operatsiyalar narxini ayt» deb so'ralganda model butun
# prays-listni bir xabarda sanab tashlardi. Bemor bunday ro'yxat so'ramaydi
# va u klinikaning obro'siga zarar qiladi. Promptdagi qoida yetarli emas —
# model «so'radi-ku» deb baribir sanab berardi, shuning uchun to'siq kodda.
#
# Nima sanaladi: «raqam + pul birligi». Oraliq («13-16 million so'm») bitta
# hisoblanadi, chunki birinchi raqamdan keyin birlik yo'q.
_PRICE_ITEM_RE = re.compile(r"\d[\d\s.,]*\s*(?:ming|mln|million|so'?m|som)", re.IGNORECASE)

# Ikkita xizmat + ularning oraliqlari — ko'pi bilan 4 ta raqam. Undan
# ortig'i ro'yxat degani. Chegarani pasaytirmang: «29 milliondan 168 million
# so'mgacha» kabi bitta javobning o'zi 2 ta raqam beradi.
_PRICE_LIST_LIMIT = 4

_PRICE_LIST_REPLY = (
    "Qaysi masala bo'yicha qiziqyapsiz? Ayting, o'shanisining narxini aniq aytaman."
)


def _clean(text: str) -> str:
    """Emoji, markdown va boshqa robot izlarini olib tashlaydi."""
    text = re.sub(r"[*_`#]+", "", text)                 # markdown belgilari
    text = re.sub(r"^\s*[-•]\s*", "", text, flags=re.M)  # ro'yxat chiziqchalari
    text = re.sub(
        "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E0-\U0001F1FF]",
        "", text,
    )
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# Shoshilinch holat — modelga ishonib o'tirilmaydi, kodda tekshiriladi.
# Anketa: «shifokorga bog'laning». Bunday xabarga AI maslahat bermaydi.
_URGENT_RE = re.compile(
    r"siyolmayapman|siya olmayapman|siyolmayman|siydik kelmayapti|"
    r"qon kel|qon ket|qonayapti|qon siy|"
    r"chidab bo'?lmas|chidab bolmas|juda qattiq og'?ri|o'?ta kuchli og'?ri|"
    r"moyagim shish|moyak burildi|moyagim burildi|"
    r"hushimdan ket|es[h]?imdan ket",
    re.IGNORECASE,
)


def is_urgent(text: str) -> bool:
    return bool(_URGENT_RE.search(text or ""))


# Bemor narx so'radimi. AI endi narxni o'zi aytadi (2026-08-11 dan), shuning
# uchun bu darhol shifokorga uzatilmaydi — faqat `chat_messages.flags` ga
# `narx` deb belgilanadi. Suhbat yakunlanganda yozuv baribir shifokorga ketadi,
# ya'ni kim narx so'raganini keyin ham ko'rish mumkin.
# «qancha» — eng keng tarqalgan narx savoli, lekin u vaqt haqida ham
# bo'lishi mumkin («qancha vaqt davom etadi»). Shuning uchun o'lchov
# so'zlari bilan kelgani hisobga olinmaydi. 2026-08-12 gacha bu yerda
# faqat «qancha turadi» bor edi va oddiy «konsultatsiya qancha?» savoli
# narx so'rovi deb tanilmasdi.
_PRICE_ASK_RE = re.compile(
    r"narx|nark|necha pul|qanchadan|puli qancha|"
    r"\bqancha\b(?!\s*(?:vaqt|kun|soat|oy|yil|kunlik|daqiqa|marta|kishi|odam|"
    r"muddat|davom))|"
    r"\bqimmat|arzon|цена|стоит|стоимость|сколько",
    re.IGNORECASE,
)


def asks_price(text: str) -> bool:
    return bool(_PRICE_ASK_RE.search(text or ""))


# Manzil so'ralganda matn bilan yo'l ko'rsatilmaydi — xaritadagi nuqta
# yuboriladi (shifokorning talabi). Bu yerda faqat savolni tanib olamiz.
_LOCATION_ASK_RE = re.compile(
    r"qayerda(?!\s*og'?ri)|qayerga|manzil|lokatsiya|joylash|"
    r"qanday bor(a|i)|qanday yetib|xarita|мест|адрес|где вы|как доехать|карт",
    re.IGNORECASE,
)


def asks_location(text: str) -> bool:
    return bool(_LOCATION_ASK_RE.search(text or ""))


# Model bemorni tushunmaganini aytdi — javob mijozga ketaveradi, lekin
# suhbat boshqa adminga uzatiladi (shifokorning talabi: noaniq xabarni
# odam ko'rsin).
_UNCLEAR_RE = re.compile(
    r"tushunmadim|tushunolmadim|tushunarsiz|aniqroq (qilib )?(yoz|ayt)|"
    r"savolingizni.{0,20}tushun",
    re.IGNORECASE,
)


def is_unclear(reply: str) -> bool:
    return bool(_UNCLEAR_RE.search(reply or ""))


# Bemor odam bilan gaplashmoqchi. Bu YAGONA holat bo'lib, unda AI o'zi
# suhbatni to'xtatib boshqa adminga uzatadi — qolgan hollarda taklif
# qilmasligi kerak (shifokorning talabi). Modelga ishonib bo'lmaydi:
# u «hozir xabar beraman» deb yozardi-yu, hech qanday signal ketmasdi.
# Shuning uchun savolning o'zi kodda aniqlanadi.
_HUMAN_ASK_RE = re.compile(
    # «… bilan gaplashmoqchiman» — eng keng tarqalgan shakl
    r"(odam|admin\w*|operator\w*|shifokor\w*|doktor\w*|o'?zi\w*)\s+bilan\s+gaplash|"
    r"tirik odam|jonli\s*(odam|operator|admin)|operator|boshqa admin|"
    r"admin(ni|ga|iz|)\s*(chaqir|ula|ulan|bog'?la|kerak)|"
    r"odamga ulan|odamga bog'?la|o'?zingiz javob ber|"
    r"человек|оператор|живой|с админом|администратор",
    re.IGNORECASE,
)


def asks_human(text: str) -> bool:
    return bool(_HUMAN_ASK_RE.search(text or ""))


# Savol mavzudan tashqari chiqdi — «kartoshka narxi», «qanday musiqa
# tinglaysiz» kabi. Bemor odam so'ramaydi, lekin javobni odam berishi
# kerak. Modelga promptda aynan shu jumla belgilangan, kod uni ushlaydi.
# «Tashxis qo'yolmayman» bunga kirmaydi — u tibbiy chegara, mavzudan
# chiqish emas.
_OFFTOPIC_RE = re.compile(
    r"savolga\s+men\s+javob\s+berolmayman|"
    r"bu\s+savolga.{0,25}javob\s+berolmayman|"
    r"javob\s+berolmayman[.\s]*boshqa\s+adminga",
    re.IGNORECASE,
)


def is_offtopic(reply: str) -> bool:
    return bool(_OFFTOPIC_RE.search(reply or ""))


# ─────────────────────────── Til va alifbo ───────────────────────────
# Promptdagi qoida yetarli emas: model kirillcha savolga lotinda javob berib
# yuboradi. Shuning uchun alifbo kodda aniqlanib, har so'rovga aniq
# ko'rsatma qo'shiladi. Tekshirilgan: 2026-08-11.
_CYRILLIC_RE = re.compile(r"[Ѐ-ӿ]")
# Faqat rus alifbosida bo'lib, o'zbek kirillida uchramaydigan harflar emas —
# ishonchli belgi: rus tiliga xos keng tarqalgan so'zlar.
# DIQQAT: bu yerga «операц…» kabi TIBBIY atamalarni qo'shmang — ular
# o'zbek kirillida ham aynan shunday yoziladi («операцияси қанча туради»)
# va bemor o'zbekcha so'raganda ruscha javob olib qolardi (2026-08-12).
# Ishonchli belgi — rus tiliga xos olmosh va yordamchi so'zlar.
_RUSSIAN_RE = re.compile(
    r"\b(здравствуйте|привет|спасибо|пожалуйста|добрый|"
    r"сколько|стоит|стоимость|цена|где|когда|почему|какой|какие|"
    r"вы|вас|вам|мне|меня|мой|моя|это|очень|нужно|хочу|можно|"
    r"врач|прием|приём|записаться|записать)\b",
    re.IGNORECASE,
)


def language_hint(text: str) -> str:
    """Shu xabar uchun til/alifbo ko'rsatmasi. Kerak bo'lmasa — bo'sh satr."""
    if not _CYRILLIC_RE.search(text or ""):
        return ""
    if _RUSSIAN_RE.search(text):
        return (
            "\n\nMUHIM: bemor hozir RUS TILIDA yozdi. "
            "Javobni to'liq rus tilida yoz."
        )
    return (
        "\n\nMUHIM: bemor hozir O'ZBEK TILIDA, KIRILL ALIFBOSIDA yozdi.\n"
        "Javobni TO'LIQ kirill alifbosida yoz. BILIM BAZASIDAGI faktlar lotin "
        "alifbosida yozilgan — ularni aynan ko'chirma, KIRILLGA O'GIRIB yoz. "
        "Javobda bitta ham lotin harfi qolmasin (raqamlar va 09:00 kabi "
        "vaqtlar bundan mustasno).\n"
        "Namuna: «Қабул душанбадан жумагача, соат 09:00 дан 16:00 гача. "
        "Тушлик 13:00 – 14:00.»"
    )


def _strip_prices(text: str) -> str:
    """Narx aytilgan gaplarni olib tashlaydi, qolganini saqlaydi."""
    parts = re.split(r"(?<=[.!?])\s+", text)
    kept = [p for p in parts if not _PRICE_ITEM_RE.search(p)]
    return " ".join(kept).strip()


# Bemor narx so'ramaganda beriladigan javob (hammasi narx bo'lib chiqsa).
_ASK_WHAT = "Bu haqda aniq nimani bilmoqchi edingiz?"


def guard(text: str, price_asked: bool = True) -> tuple[str, list[str]]:
    """Yakuniy to'siq. Qaytaradi: (javob, buzilgan qoidalar ro'yxati).

    `price_asked=False` — bemor narx so'ramagan. Model buni tez-tez
    buzadi: «varikosele» degan bitta so'zga ham narxni qo'shib yuboradi
    (2026-08-12 da tekshirilgan). Promptdagi qoida yetmadi, shuning uchun
    narx aytilgan GAPLAR javobdan olib tashlanadi — qolgan matn saqlanadi.
    """
    hits: list[str] = []
    text = _clean(text)

    if _MEDFAST_RE.search(text):
        hits.append("eski_klinika")
        text = _MEDFAST_RE.sub("Sintez Lab", text)

    if len(_PRICE_ITEM_RE.findall(text)) > _PRICE_LIST_LIMIT:
        hits.append("narx_royxati")
        return _PRICE_LIST_REPLY, hits

    if not price_asked and _PRICE_ITEM_RE.search(text):
        hits.append("soralmagan_narx")
        text = _strip_prices(text) or _ASK_WHAT

    return text, hits


# ─────────────────────────── Modelga so'rov ───────────────────────────
async def chat(
    user_text: str,
    history: list[dict] | None = None,
    context: str | None = None,
) -> tuple[str | None, list[str]]:
    """Suhbat javobi.

    `history` — [{"role": "user"|"model", "text": "..."}] ko'rinishida,
    eng eskisi birinchi. Model o'chirilgan yoki xato bo'lsa `(None, [...])`.
    """
    if not AI_ENABLED or not AI_API_KEY:
        return None, ["ai_ochiq_emas"]

    ctx = context if context is not None else await build_context()
    contents = []
    for m in (history or [])[-HISTORY_LIMIT:]:
        contents.append({"role": m["role"], "parts": [{"text": m["text"]}]})
    contents.append({"role": "user", "parts": [{"text": user_text}]})

    # Til ko'rsatmasi IKKI joyda: promptning boshida va oxirida. Bitta joyda
    # (oxirida) turganda model uni 16 000 belgilik kontekst ichida e'tiborsiz
    # qoldirib, ruscha savolga o'zbekcha javob berib qo'ygan edi.
    hint = language_hint(user_text)
    instruction = (hint.strip() + "\n\n" if hint else "") + persona.system_prompt(ctx) + hint
    payload = {
        "systemInstruction": {"parts": [{"text": instruction}]},
        "contents": contents,
        "generationConfig": {
            # Yuqori temperatura — bir xil savolga bir xil jumla qaytmasligi uchun.
            "temperature": 0.9,
            "topP": 0.95,
            "maxOutputTokens": 500,
        },
        # Tibbiy mavzular (jinsiy salomatlik) standart filtrga tushib qolmasin.
        "safetySettings": [
            {"category": c, "threshold": "BLOCK_ONLY_HIGH"}
            for c in (
                "HARM_CATEGORY_HARASSMENT",
                "HARM_CATEGORY_HATE_SPEECH",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "HARM_CATEGORY_DANGEROUS_CONTENT",
            )
        ],
    }

    url = API_URL.format(model=AI_MODEL)
    try:
        # Gemini vaqti-vaqti bilan 500/503 qaytaradi (o'z tomonidagi
        # vaqtinchalik nosozlik). Bir marta qayta urinamiz — aks holda
        # bemor sababsiz «nosozlik chiqdi» degan javob olardi.
        async with httpx.AsyncClient(timeout=30) as client:
            for attempt in range(2):
                r = await client.post(
                    url, json=payload, headers={"x-goog-api-key": AI_API_KEY}
                )
                if r.status_code < 500 or attempt:
                    break
                log.warning("Gemini %s — qayta urinamiz", r.status_code)
                await asyncio.sleep(1.5)
        if r.status_code != 200:
            log.warning("Gemini %s: %s", r.status_code, r.text[:300])
            return None, [f"http_{r.status_code}"]

        data = r.json()
        cands = data.get("candidates") or []
        if not cands:
            log.warning("Gemini javobi bo'sh: %s", str(data)[:300])
            return None, ["bosh_javob"]

        raw = "".join(
            p.get("text", "") for p in cands[0].get("content", {}).get("parts", [])
        )
        if not raw.strip():
            return None, ["bosh_matn"]

        return guard(raw, price_asked=asks_price(user_text))
    except Exception as e:
        log.warning("Gemini xatosi: %s", e)
        return None, ["xato"]


# ─────────────────────────── Ovozli xabar → matn ───────────────────────────
# Shifokorning qarori: ovozli xabar matnga o'girilsa AI unga darhol javob
# beradi. O'girib bo'lmasa — bemordan yozib yuborish so'raladi va suhbat
# boshqa adminga uzatiladi. Rasm esa O'QILMAYDI: shifokor masofadan turib
# tashxis qo'ymaydi, rasm shunchaki unga yetkaziladi.
_TRANSCRIBE_PROMPT = """
Bu ovozli xabarni so'zma-so'z matnga o'gir. Xabar o'zbek (lotin yoki kirill)
yoki rus tilida bo'lishi mumkin — qaysi tilda aytilgan bo'lsa, o'sha tilda yoz.

Faqat matnning o'zini qaytar: izoh, sarlavha, tirnoq belgisi qo'shma.

Agar ovoz eshitilmasa, shovqin bo'lsa, nutq umuman bo'lmasa yoki aytilgan
gapni aniq ajratib bo'lmasa — hech narsa taxmin qilmasdan faqat shu so'zni
yoz: NOANIQ
""".strip()

# Juda qisqa natija ham ishonchsiz: «ha», «a» kabi bitta bo'g'in ko'pincha
# shovqindan chiqadi.
_MIN_TRANSCRIPT = 4


async def transcribe(data: bytes, mime: str = "audio/ogg") -> str | None:
    """Ovozli xabar matni, yoki ishonchli o'girib bo'lmasa `None`."""
    if not AI_ENABLED or not AI_API_KEY:
        return None

    import base64

    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": _TRANSCRIBE_PROMPT},
                {"inlineData": {"mimeType": mime,
                                "data": base64.b64encode(data).decode()}},
            ],
        }],
        # Transkripsiyada ijod kerak emas — nol temperatura.
        "generationConfig": {"temperature": 0, "maxOutputTokens": 500},
    }

    url = API_URL.format(model=AI_MODEL)
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                url, json=payload, headers={"x-goog-api-key": AI_API_KEY}
            )
        if r.status_code != 200:
            log.warning("Transkripsiya %s: %s", r.status_code, r.text[:200])
            return None
        cands = r.json().get("candidates") or []
        if not cands:
            return None
        text = "".join(
            p.get("text", "") for p in cands[0].get("content", {}).get("parts", [])
        ).strip()
    except Exception as e:
        log.warning("Transkripsiya xatosi: %s", e)
        return None

    if not text or len(text) < _MIN_TRANSCRIPT or "NOANIQ" in text.upper():
        return None
    return text


# ─────────────────────────── Eski chaqiruv joyi ───────────────────────────
async def answer(question: str, context: str = "") -> str | None:
    """Bitta savol — bitta javob (xotirasiz).

    Eski «Murojaat» oqimi shu funksiyani chaqiradi. Yangi jonli suhbat
    `chat()` dan foydalanadi.
    """
    reply, _ = await chat(question, history=None, context=context or None)
    return reply
