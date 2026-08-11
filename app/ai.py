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

import logging
import re
import time

import httpx

from app import repo, persona
from app.config import AI_API_KEY, AI_ENABLED, AI_MODEL
from app.db import SessionLocal
from app.knowledge import PHONE, knowledge_text

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
_PRICE_RE = re.compile(
    r"(\d[\d\s.,]{2,})\s*(so'm|som|sum|ming|mln|million|\$|dollar|usd)",
    re.IGNORECASE,
)
_MEDFAST_RE = re.compile(r"med\s*fast|ozod\s*sharq", re.IGNORECASE)


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


# Anketa: «Qaysi savollarda AI albatta suhbatni sizga uzatishi kerak? — narx
# so'ralsa». Model to'g'ri javob bergan taqdirda ham shifokor xabardor bo'ladi.
_PRICE_ASK_RE = re.compile(
    r"narx|nark|qancha turadi|qancha bo'?ladi|necha pul|qanchadan|puli qancha|"
    r"\bqimmat|arzon|цена|стоит|стоимость|сколько сто",
    re.IGNORECASE,
)


def asks_price(text: str) -> bool:
    return bool(_PRICE_ASK_RE.search(text or ""))


# ─────────────────────────── Til va alifbo ───────────────────────────
# Promptdagi qoida yetarli emas: model kirillcha savolga lotinda javob berib
# yuboradi. Shuning uchun alifbo kodda aniqlanib, har so'rovga aniq
# ko'rsatma qo'shiladi. Tekshirilgan: 2026-08-11.
_CYRILLIC_RE = re.compile(r"[Ѐ-ӿ]")
# Faqat rus alifbosida bo'lib, o'zbek kirillida uchramaydigan harflar emas —
# ishonchli belgi: rus tiliga xos keng tarqalgan so'zlar.
_RUSSIAN_RE = re.compile(
    r"\b(здравствуйте|привет|сколько|цена|где|когда|можно|спасибо|"
    r"добрый|день|как|что|это|врач|прием|приём|записаться|операц\w*)\b",
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
        "\n\nMUHIM: bemor hozir O'ZBEK TILIDA, KIRILL ALIFBOSIDA yozdi. "
        "Javobni ham to'liq kirill alifbosida yoz — bitta so'zni ham lotinda "
        "qoldirma. Masalan: «Ассалому алайкум! Қандай саволингиз бор?»"
    )


def guard(text: str) -> tuple[str, list[str]]:
    """Yakuniy to'siq. Qaytaradi: (javob, buzilgan qoidalar ro'yxati)."""
    hits: list[str] = []
    text = _clean(text)

    if _PRICE_RE.search(text):
        hits.append("narx")
        text = (
            "Narxni ko'rikdan keyin shifokorning o'zi aytadi — har bir holat "
            f"boshqacha bo'ladi. Aniqlashtirish uchun {PHONE} raqamiga qo'ng'iroq qiling."
        )
    elif _MEDFAST_RE.search(text):
        hits.append("eski_klinika")
        text = _MEDFAST_RE.sub("Sintez Lab", text)

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

    instruction = persona.system_prompt(ctx) + language_hint(user_text)
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
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                url, json=payload, headers={"x-goog-api-key": AI_API_KEY}
            )
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

        return guard(raw)
    except Exception as e:
        log.warning("Gemini xatosi: %s", e)
        return None, ["xato"]


# ─────────────────────────── Eski chaqiruv joyi ───────────────────────────
async def answer(question: str, context: str = "") -> str | None:
    """Bitta savol — bitta javob (xotirasiz).

    Eski «Murojaat» oqimi shu funksiyani chaqiradi. Yangi jonli suhbat
    `chat()` dan foydalanadi.
    """
    reply, _ = await chat(question, history=None, context=context or None)
    return reply
