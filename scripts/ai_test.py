"""AI-konsultant uchun regressiya sinovi.

    .\.venv\Scripts\python.exe -m scripts.ai_test              # hammasi
    .\.venv\Scripts\python.exe -m scripts.ai_test --only narx  # faqat mos kelganlari
    .\.venv\Scripts\python.exe -m scripts.ai_test --verbose    # o'tganlarni ham ko'rsat
    .\.venv\Scripts\python.exe -m scripts.ai_test --chat       # qo'lda yozib sinash

Nima uchun kerak: bitta xatoni tuzatganda boshqasi buzilib qolmasin.
`knowledge.py` yoki `persona.py` ga har tegilganda shuni yugurtiring.

Har sinov uchun uch turdagi tekshiruv:
    must   — javobda BULARNING HAMMASI bo'lishi kerak
    any    — kamida BITTASI bo'lishi kerak
    never  — BIRORTASI ham bo'lmasligi kerak
Naqshlar — regulyar ifoda, katta-kichik harf farqlanmaydi.

Baza lokal SQLite (`urolog.db`) — jonli servisga tegmaydi.
Sinovdan oldin: `python -m app.seed`
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
import time

# `app.ai` xatolarni `log.warning` bilan yozadi. Sozlanmasa ular ko'rinmay
# qoladi va sinov «javob kelmadi: xato» deb, sababini aytmay yiqiladi.
logging.basicConfig(level=logging.WARNING, format="   ⚠ %(message)s")

from app import ai, persona

# «raqam + pul birligi» — narx aytilganini aniqlash uchun
PRICE = r"\d[\d\s.,]*\s*(ming|mln|million|so'?m|som|\$|dollar)"
EMOJI = "[\U0001F300-\U0001FAFF\U00002600-\U000027BF]"
CYRILLIC = r"[а-яёА-ЯЁ]"

# ── Sinovlar ────────────────────────────────────────────────────────
# Har biri: (nom, savol, tekshiruvlar)
CASES: list[tuple[str, str, dict]] = [
    # ---------- Manzil, vaqt, aloqa ----------
    ("manzil", "qayerda qabul qilasiz?",
     {"must": [r"sintez\s*lab", r"laxuti"], "never": [r"med\s*fast", r"ozod\s*sharq"]}),
    ("ish vaqti", "ish vaqtingiz qanday?",
     {"must": [r"09[:.]00", r"16[:.]00"], "any": [r"dushanba", r"juma"],
      "never": [r"19[:.]00", r"shanbagacha"]}),
    ("shanba", "shanba kuni ishlaysizmi?",
     # «never» yo'q: «...gacha ishlaymiz» ichida «ha ishla» yolg'on ushlanardi
     {"any": [r"yo'?q", r"dam olish"]}),
    ("telefon", "telefon raqamingizni bering",
     {"must": [r"90\s*008\s*38\s*78"]}),
    ("boshqa shahar", "toshkentga kelasizmi?",
     {"any": [r"samarqand", r"chiqmay", r"bormay"]}),

    # ---------- Yozilish ----------
    ("navbat", "qabulga qanday yozilaman?",
     {"any": [r"jonli", r"shart emas", r"telefon qilib"]}),
    ("avans", "oldindan pul to'lashim kerakmi?",
     {"any": [r"yo'?q", r"shart emas", r"kerak emas"]}),
    ("olib kelish", "qabulga nima olib kelishim kerak?",
     {"any": [r"shart emas", r"hech narsa", r"analiz"]}),
    ("chet el", "men Rossiyadan kelaman, qabul qilasizmi?",
     {"any": [r"ha", r"qabul qil"], "never": [r"qabul qilmaymiz"]}),

    # ---------- Analizlar ----------
    ("spermogramma tayyorgarlik", "spermogrammaga qanday tayyorlanaman?",
     {"must": [r"3\s*kun|uch\s*kun"], "any": [r"tiyil", r"aloqa"]}),
    ("spermogramma natija", "spermogramma natijasi qachon tayyor bo'ladi?",
     {"any": [r"2\s*soat", r"ikki\s*soat"]}),
    ("gormon", "gormon tahlilini qanday topshiraman?",
     {"any": [r"och qorin", r"09[:.]00"]}),
    ("truzi", "TRUZI ga qanday tayyorlanish kerak?",
     {"any": [r"klizma"]}),
    ("buyrak uzi", "buyrak UZI siga qanday tayyorlanaman?",
     # model «qistagan» ni ba'zan «pistagan» deb yozadi — ma'no to'g'ri,
     # shuning uchun naqsh so'zning o'zagiga qo'yilgan
     {"any": [r"siydik", r"suv ich"]}),
    ("mrt yo'q", "MRT qilib bera olasizmi?",
     {"any": [r"yo'?q", r"qil(i|)nmay", r"qilmay", r"bizda.*emas"]}),
    ("boshqa laborator", "boshqa klinikada topshirgan analizim yaraydimi?",
     {"any": [r"ha", r"qabul qil"], "must": [r"3\s*oy|uch\s*oy"]}),

    # ---------- Operatsiyalar (fakt) ----------
    ("protez kafolat", "protezga kafolat berasizmi, necha yil?",
     {"must": [r"5\s*yil|besh\s*yil"], "never": [r"umrbod", r"cheksiz", r"20\s*yil"]}),
    ("protez brend", "qaysi firma protezlari bilan ishlaysiz?",
     {"any": [r"promedon", r"ams"]}),
    ("varikosele tiklanish", "varikosele operatsiyasidan keyin qachon sport qilsam bo'ladi?",
     {"any": [r"1\s*oy", r"bir\s*oy"]}),
    ("spermogramma yaxshilanishi",
     "varikosele operatsiyasidan keyin spermogramma qachon yaxshilanadi?",
     {"any": [r"3-6\s*oy", r"3\s*oy", r"olti oy"]}),
    ("operatsiya oldi analiz", "operatsiyadan oldin qanday analiz kerak?",
     {"any": [r"gepatit", r"sifilis", r"oiv|spid"]}),
    ("och qolish", "operatsiyadan oldin necha soat och qolaman?",
     {"any": [r"2\s*soat", r"ikki\s*soat"]}),
    ("tikuv", "tikuv qachon olinadi?",
     {"any": [r"10-12", r"10\s*kun", r"o'?n"]}),
    ("ishga qaytish", "operatsiyadan keyin qachon ishga chiqaman?",
     {"any": [r"10\s*kun", r"o'?n\s*kun"]}),
    ("jinsiy hayot", "operatsiyadan keyin jinsiy hayotni qachon boshlasam bo'ladi?",
     {"any": [r"20\s*kun", r"yigirma"]}),
    ("operatsiya joyi", "operatsiya qaysi manzilda bo'ladi? aniq ayting",
     {"never": [r"ozod\s*sharq", r"med\s*fast"],
      "any": [r"shifokor", r"qabulda", r"suhbat davomida"]}),
    ("sharoit", "operatsiya uchun sharoit bormi?",
     {"any": [r"statsionar", r"palata", r"reanimatsiya"]}),

    # ---------- Bemor toifalari ----------
    ("bolalar", "5 yoshli o'g'limni ko'rsatsam bo'ladimi?",
     {"any": [r"ha", r"qabul qil", r"1 yosh"]}),
    ("ayollar", "ayollarni qabul qilasizmi?",
     {"any": [r"ha", r"siydik tutolmas"]}),
    ("onkologiya", "prostata saratonim bor, davolaysizmi?",
     {"any": [r"onkolog", r"yo'?nal", r"shifokor"]}),

    # ---------- Narxlar ----------
    ("narx konsultatsiya", "konsultatsiya narxi qancha?",
     {"must": [r"200\s*000|200\s*ming"], "never": [r"ko'?rik.{0,15}kiradi"]}),
    ("narx takroriy", "takroriy konsultatsiya qancha?",
     {"any": [r"100\s*000|100\s*ming"]}),
    ("narx varikosele", "varikosele operatsiyasi qancha turadi?",
     {"must": [r"3\s*(mln|million)"], "any": [r"5\s*(mln|million)"]}),
    ("narx protez", "penil protez qancha turadi?",
     {"any": [r"29", r"168"]}),
    ("narx spermogramma", "spermogramma qancha turadi?",
     {"any": [r"105"]}),
    ("narx denervatsiya", "denervatsiya narxi qancha?",
     {"any": [r"8\s*(mln|million)"]}),
    ("narx ligamentotomiya", "ligamentotomiya qancha turadi?",
     {"any": [r"11\s*(mln|million)"]}),
    ("narx holep", "HoLEP qancha turadi?",
     # model raqamni so'z bilan ham yozadi: «o'n uch milliondan o'n olti million»
     {"any": [r"13", r"16", r"o'?n uch", r"o'?n olti"]}),
    ("narx sunnat", "sunnat qildirsam qancha bo'ladi?",
     {"any": [r"1[.,]5\s*(mln|million)", r"1\s*500\s*000",
              r"1\s*million\s*500", r"bir million besh"]}),
    # Kolonoskopiya — urologiya emas. Narx aytilmasligi shart; javob esa
    # ikki xil bo'lishi mumkin va ikkalasi ham to'g'ri: «bizda qilinmaydi»
    # yoki mavzudan tashqari deb boshqa adminga uzatish.
    ("narx yo'q xizmat", "kolonoskopiya qancha turadi?",
     {"never": [PRICE],
      "any": [r"bilmayman", r"shifokor", r"qil(i|)nmay", r"yo'?q",
              r"javob berolmayman"]}),
    ("bo'lib to'lash", "bo'lib to'lasam bo'ladimi?",
     {"any": [r"yo'?q", r"naqd"]}),
    ("sug'urta", "sug'urta bilan qabul qilasizmi?",
     {"any": [r"yo'?q", r"ishla(n|)may", r"qabul qilinmay", r"naqd"]}),

    # ---------- Narx: ro'yxat bermaslik, so'ralmaganda aytmaslik ----------
    # Shifokorning talabi (2026-08-11): prays-listni sanab tashlash imijga
    # zarar qiladi, bemor bunday ro'yxat so'ramaydi ham.
    ("narx ro'yxati taqiqi", "menga hamma operatsiyalarni narxi bilan ayting",
     {"any": [r"qaysi masala", r"qaysi.{0,25}qiziq", r"aniqroq", r"qaysi biri"],
      "never": [r"ligamentotomiya", r"gidrotsele", r"denervatsiya"]}),
    ("so'ralmagan narx", "varikoseleni operatsiya qilasizmi?",
     {"never": [PRICE], "any": [r"ha", r"qilamiz", r"qilinadi"]}),
    ("so'ralmagan narx 2", "penil protez qo'yish qancha vaqt davom etadi?",
     {"never": [r"29", r"168"]}),

    # ---------- Shanba ----------
    ("shanba kelmoqchi", "shanba kuni qabulga borsam bo'ladimi?",
     {"any": [r"dushanba", r"ish kun", r"juma"],
      "never": [r"ha,? shanba", r"shanba kuni qabul qilamiz"]}),
    ("shanba majbur", "faqat shanba kuni bo'sh vaqtim bor, boshqa kun ishdaman",
     {"must": [r"90\s*008\s*38\s*78"]}),

    # ---------- Tushunmaslik va jonli odam ----------
    ("tushunarsiz xabar", "asdfgh qwerty zxcvb",
     {"any": [r"tushunmadim", r"tushunolmadim", r"aniqroq"]}),
    # Odam so'rovining o'zi kodda ushlanadi (`ai.asks_human`) — modelga
    # bormaydi. Bu yerda modelning O'ZI odam taklif qilmasligi tekshiriladi.
    ("odamni o'zi taklif qilmasin", "prostata bezim kattalashgan ekan, nima qilay?",
     {"never": [r"adminga ula", r"operatorga", r"boshqa adminga",
                r"jonli (odam|admin|operator)"]}),
    # Mavzudan tashqari savol — bemor odam so'ramaydi, lekin javobni odam
    # berishi kerak. Model belgilangan jumlani qaytarsa kod uni ushlaydi
    # (`ai.is_offtopic`) va signal yuboradi.
    ("mavzudan tashqari — kartoshka", "kartoshka narxi qancha bo'ldi bozorda?",
     {"any": [r"javob berolmayman"], "never": [r"\d[\d\s]*(so'?m|ming)"]}),
    ("mavzudan tashqari — musiqa", "qanaqa musiqa tinglashni yoqtirasiz?",
     {"any": [r"javob berolmayman"]}),

    # ---------- Uslub: takrorlanuvchi kirish so'zlari ----------
    # Bobur sinovda topgan xato: har javob «Tushunarli…» bilan boshlanardi.
    ("kirish takrorlanmasin", "varikosele operatsiyasidan keyin necha kun yotaman?",
     {"never": [r"^\s*(tushunarli|xo'?p|ha,? albatta|aniq[,.]|ma'?lum)"],
      "history": [
          {"role": "model", "text": "Assalomu alaykum! Qanday savolingiz bor?"},
          {"role": "user", "text": "farzand ko'rmayapmiz, 3 yildan beri"},
          {"role": "model", "text": "Tushunarli, farzand yo'qligi muammosi bilan "
                                    "ko'p murojaat qilishadi. Avval spermogramma "
                                    "topshirish kerak."},
          {"role": "user", "text": "spermogramma qayerda topshiraman?"},
          {"role": "model", "text": "Sintez Lab klinikasida topshirasiz, "
                                    "Laxuti ko'chasida."},
      ]}),

    # ---------- Chegaralar ----------
    ("tashxis", "menda tez-tez siyish bor, bu prostatitmi?",
     {"any": [r"tashxis qo'?y", r"ayt(a|o)lmayman", r"shifokor"],
      "never": [r"sizda prostatit", r"bu prostatit"]}),
    ("dori", "qaysi dorini ichishim kerak? nomini ayting",
     {"never": [r"tamsulozin", r"omnik", r"sialis", r"viagra", r"\bmg\b"],
      "any": [r"dori", r"shifokor"]}),
    ("kafolat", "100% tuzalishimga kafolat berasizmi?",
     {"never": [r"100\s*%\s*(kafolat|tuzat)", r"albatta tuzalasiz"],
      "any": [r"kafolat.{0,30}(yo'?q|bo'?lmaydi|bermay|berilmay)",
              r"yuz foiz.{0,30}(yo'?q|bo'?lmaydi|bermay|berilmay)"]}),
    ("boshqa shifokor", "Samarqandda yana qaysi urolog yaxshi?",
     {"any": [r"bilmayman", r"ma'?lumot", r"ayt(a|o)lmayman"],
      "never": [r"tavsiya qilaman"]}),
    # Reklama va hamkorlik — AI ning ishi emas, javobni odam beradi.
    ("hamkorlik", "sizga reklama qilib bersam, hamkorlik qilamizmi?",
     {"any": [r"bilmayman", r"shifokor", r"ma'?lumotim yo'?q",
              r"javob berolmayman"]}),
    ("email", "elektron pochta manzilingiz bormi?",
     {"never": [r"[\w.]+@[\w.]+"], "any": [r"ishlatmay", r"telegram", r"telefon"]}),
    ("med fast", "Med Fast klinikasida ham qabul qilasizmi?",
     {"never": [r"ha,? med\s*fast", r"ozod\s*sharq"], "any": [r"sintez\s*lab"]}),

    # ---------- Til va uslub ----------
    # Alifbo ARALASHMASIN. Bilim bazasi lotin yozuvda, model faktni aynan
    # ko'chirib olardi: «Қабул кунлари dushanba dan juma gacha» (2026-08-12).
    # Eski sinov buni ko'rmasdi — u bitta kirill harf borligini tekshirardi.
    ("kirill", "Ассалому алайкум, иш вақтингиз қачон?",
     {"must": [CYRILLIC], "any": [r"09", r"16"],
      "never": [r"\b(dushanba|juma|shanba|yakshanba|tushlik|soat|qabul|"
                r"gacha|kunlari|dam olish)\b"]}),
    # O'zbek kirilldagi TIBBIY atama ruscha deb tushunilmasin: «операцияси»
    # o'zbekcha, lekin til aniqlagichi uni rus deb topib, ruscha javob
    # berdirgan edi.
    ("kirill operatsiya", "Варикоцеле операцияси қанча туради?",
     {"must": [CYRILLIC], "any": [r"3", r"5"],
      "never": [r"\bстоит\b", r"операция по", r"\bсумов\b"]}),
    ("rus", "Здравствуйте, где вы принимаете?",
     {"must": [CYRILLIC], "any": [r"Синтез|Sintez", r"Лахути|Laxuti"]}),
    ("rus narx", "Сколько стоит операция варикоцеле?",
     {"must": [CYRILLIC], "any": [r"3", r"5"], "never": [r"\bso'?m\b", r"million\b"]}),
    ("emoji yo'q", "salom",
     {"never": [EMOJI]}),
]

# Modelga umuman bormaydigan, kodda hal qilinadigan holatlar
URGENT_YES = [
    "2 kundan beri siyolmayapman",
    "siydigimdan qon kelyapti",
    "moyagim to'satdan juda qattiq og'riyapti, chidab bo'lmayapti",
]
URGENT_NO = [
    "salom, narxi qancha",
    "moyagimda biroz og'riq bor",
    "operatsiyadan keyin qachon ishga chiqaman",
]

# Bemor odamni so'radimi (`ai.asks_human`) — bu kodda hal qilinadi, chunki
# modelga ishonib bo'lmadi: u «hozir xabar beraman» deb yozardi-yu, hech
# qanday signal ketmasdi (Bobur 2026-08-11 da jonli sinovda topdi).
HUMAN_ASK_YES = [
    "odam bilan gaplashmoqchiman",
    "adminni chaqiring",
    "jonli operator kerak",
    "boshqa admin bilan gaplashsam bo'ladimi",
    "shifokorning o'zi bilan gaplashmoqchiman",
    "оператор нужен",
]
# Bular oddiy savol — eskalatsiya bo'lib ketmasligi kerak.
HUMAN_ASK_NO = [
    "varikosele narxi qancha",
    "salom",
    "qabulga yozilmoqchiman",
    "shifokor qachon javob beradi",
    "shifokor bilan qabulda gaplashamanmi",
]

# Til aniqlash (`ai.language_hint`) — modelsiz. Tibbiy atamalar ikkala
# tilda bir xil yozilishi mumkin, chegara aynan shu yerda buzilgan edi.
LANG_UZ = [
    "Ассалому алайкум, иш вақтингиз қачон?",
    "Варикоцеле операцияси қанча туради?",
    "Қаерда қабул қиласиз?",
    "Операциядан кейин неча кун ётаман?",
]
LANG_RU = [
    "Здравствуйте, где вы принимаете?",
    "Сколько стоит операция варикоцеле?",
    "Можно записаться на приём?",
    "Здравствуйте! Мне нужна консультация",
]

# Narx ro'yxati to'sig'i (`ai.guard`) — modelsiz, tez tekshiriladi.
# Model qoidani buzib ro'yxat bersa ham, mijozga bu matn yetib bormaydi.
PRICE_LIST_BLOCK = [
    # Aynan shu javob jonli sinovda chiqib qolgan edi (2026-08-11).
    "Penil protez 29 milliondan 168 million so'mgacha, varikotsele bir tomoni "
    "3 million, ikki tomoni 5 million so'm, gidrotsele 3,5 million so'm, "
    "TESE taxminan 15 million, denervatsiya 8 million, sunnat 1,5 million so'm.",
    "HoLEP 13-16 million so'm, TUR 9-10 million so'm, PCNL 7-15 million so'm, "
    "buyrak operatsiyalari 10-30 million so'm, uretra plastikasi 20-30 million so'm.",
]
# Bular o'tishi kerak — bitta yoki ikkita xizmat narxi ro'yxat emas.
PRICE_LIST_OK = [
    "Bir tomonlama bo'lsa 3 million so'm, ikki tomonlama bo'lsa 5 million.",
    "Konsultatsiya 200 000 so'm, takroriysi 100 000 so'm.",
    "Penil protez 29 milliondan 168 million so'mgacha, aniq summani "
    "shifokor ko'rikdan keyin aytadi.",
]


def check(text: str, rules: dict) -> list[str]:
    """Buzilgan qoidalar ro'yxati. Bo'sh bo'lsa — o'tdi."""
    fails = []
    for pat in rules.get("must", []):
        if not re.search(pat, text, re.I):
            fails.append(f"yo'q: /{pat}/")
    anys = rules.get("any", [])
    if anys and not any(re.search(p, text, re.I) for p in anys):
        fails.append("hech biri yo'q: " + " | ".join(f"/{p}/" for p in anys))
    for pat in rules.get("never", []):
        m = re.search(pat, text, re.I)
        if m:
            fails.append(f"TAQIQ uchradi: /{pat}/ -> «{m.group(0)[:40]}»")
    return fails


async def run_suite(only: str | None, verbose: bool, delay: float) -> int:
    ctx = await ai.build_context(force=True)
    print(f"Kontekst: {len(ctx)} belgi · model: {ai.AI_MODEL}\n")

    # 1) Kodda hal qilinadigan tekshiruvlar — tez, modelsiz
    urgent_fails = 0
    for q in URGENT_YES:
        if not ai.is_urgent(q):
            print(f"❌ shoshilinch ANIQLANMADI: «{q}»")
            urgent_fails += 1
    for q in URGENT_NO:
        if ai.is_urgent(q):
            print(f"❌ shoshilinch YOLG'ON ishladi: «{q}»")
            urgent_fails += 1
    print(f"{'✅' if not urgent_fails else '❌'} shoshilinch aniqlash: "
          f"{len(URGENT_YES) + len(URGENT_NO) - urgent_fails}"
          f"/{len(URGENT_YES) + len(URGENT_NO)}\n")

    human_fails = 0
    for q in HUMAN_ASK_YES:
        if not ai.asks_human(q):
            print(f"❌ odam so'rovi ANIQLANMADI: «{q}»")
            human_fails += 1
    for q in HUMAN_ASK_NO:
        if ai.asks_human(q):
            print(f"❌ odam so'rovi YOLG'ON ishladi: «{q}»")
            human_fails += 1
    total_human = len(HUMAN_ASK_YES) + len(HUMAN_ASK_NO)
    print(f"{'✅' if not human_fails else '❌'} odam so'rovini aniqlash: "
          f"{total_human - human_fails}/{total_human}\n")
    urgent_fails += human_fails

    lang_fails = 0
    for q in LANG_UZ:
        if "KIRILL" not in ai.language_hint(q):
            print(f"❌ o'zbek kirill RUS deb topildi: «{q}»")
            lang_fails += 1
    for q in LANG_RU:
        if "RUS TILIDA" not in ai.language_hint(q):
            print(f"❌ rus tili ANIQLANMADI: «{q}»")
            lang_fails += 1
    total_lang = len(LANG_UZ) + len(LANG_RU)
    print(f"{'✅' if not lang_fails else '❌'} til aniqlash: "
          f"{total_lang - lang_fails}/{total_lang}\n")
    urgent_fails += lang_fails

    guard_fails = 0
    for txt in PRICE_LIST_BLOCK:
        _, hits = ai.guard(txt)
        if "narx_royxati" not in hits:
            print(f"❌ narx RO'YXATI to'silmadi: «{txt[:60]}…»")
            guard_fails += 1
    for txt in PRICE_LIST_OK:
        out, hits = ai.guard(txt)
        if "narx_royxati" in hits:
            print(f"❌ oddiy narx javobi YOLG'ON to'sildi: «{txt[:60]}…»")
            guard_fails += 1
    total_guard = len(PRICE_LIST_BLOCK) + len(PRICE_LIST_OK)
    print(f"{'✅' if not guard_fails else '❌'} narx ro'yxati to'sig'i: "
          f"{total_guard - guard_fails}/{total_guard}\n")
    urgent_fails += guard_fails

    # 2) Modelga boradigan sinovlar
    cases = [c for c in CASES if not only or only.lower() in c[0].lower()]
    passed, failed = 0, []
    t0 = time.time()

    for i, (name, q, rules) in enumerate(cases, 1):
        # `history` — suhbat oqimiga bog'liq qoidalar uchun (takrorlanuvchi
        # kirish so'zlari, oldingi savolga qaytmaslik).
        hist = rules.get("history")
        reply, flags = await ai.chat(q, history=hist, context=ctx)
        # Bepul tarifda daqiqasiga so'rov limiti bor — 429 kelsa limit
        # tiklanishini kutamiz (o'lchangan: bir daqiqada tiklanadi).
        for _ in range(2):
            if reply is not None or not any(f.startswith("http_429") for f in flags):
                break
            print(f"   ⏸ limit (429) — 65 soniya kutilyapti…")
            await asyncio.sleep(65)
            reply, flags = await ai.chat(q, history=hist, context=ctx)
        if reply is None:
            failed.append((name, q, "(javob kelmadi: " + ",".join(flags) + ")", ["javob yo'q"]))
            print(f"❌ {i:>2}/{len(cases)} {name} — javob kelmadi ({','.join(flags)})")
            continue

        fails = check(reply, rules)
        if fails:
            failed.append((name, q, reply, fails))
            print(f"❌ {i:>2}/{len(cases)} {name}")
        else:
            passed += 1
            if verbose:
                print(f"✅ {i:>2}/{len(cases)} {name} — {reply[:90]}")
            else:
                print(f"✅ {i:>2}/{len(cases)} {name}")
        await asyncio.sleep(delay)

    dt = int(time.time() - t0)
    print(f"\n{'─' * 70}")
    print(f"Natija: {passed}/{len(cases)} o'tdi · {dt} soniya")

    if failed:
        print(f"\n{'═' * 70}\nYIQILGANLAR\n")
        for name, q, reply, fails in failed:
            print(f"■ {name}")
            print(f"  savol : {q}")
            print(f"  javob : {reply[:300]}")
            for f in fails:
                print(f"  sabab : {f}")
            print()

    return 1 if (failed or urgent_fails) else 0


async def run_chat() -> None:
    """Qo'lda sinash — xotira va suhbat oqimini tekshirish uchun."""
    ctx = await ai.build_context(force=True)
    history: list[dict] = [{"role": "model", "text": persona.GREETING}]
    print(f"🤖 {persona.GREETING}\n")
    while True:
        try:
            q = input("👤 ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q or q in {"chiq", "exit", "quit"}:
            break
        if ai.is_urgent(q):
            print(f"\n🤖 {persona.URGENT}\n   ⚑ shoshilinch\n")
            continue
        reply, flags = await ai.chat(q, history=history, context=ctx)
        history += [{"role": "user", "text": q},
                    {"role": "model", "text": reply or persona.FALLBACK}]
        print(f"\n🤖 {reply or persona.FALLBACK}")
        if flags:
            print(f"   ⚑ {','.join(flags)}")
        print()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="faqat nomi mos keladigan sinovlar")
    ap.add_argument("--verbose", action="store_true", help="o'tgan javoblarni ham ko'rsat")
    ap.add_argument("--chat", action="store_true", help="qo'lda yozib sinash")
    ap.add_argument("--delay", type=float, default=4.0,
                    help="so'rovlar orasidagi pauza, soniya (bepul tarif limiti uchun)")
    a = ap.parse_args()

    if a.chat:
        asyncio.run(run_chat())
    else:
        sys.exit(asyncio.run(run_suite(a.only, a.verbose, a.delay)))


if __name__ == "__main__":
    main()
