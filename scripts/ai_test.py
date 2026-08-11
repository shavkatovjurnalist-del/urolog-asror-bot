"""AI-konsultantni lokal sinash.

    .\.venv\Scripts\python.exe -m scripts.ai_test           # tayyor savollar
    .\.venv\Scripts\python.exe -m scripts.ai_test --chat    # qo'lda yozib sinash

Baza lokal SQLite (`urolog.db`) — jonli servisga tegmaydi.
Sinovdan oldin kontent yuklangan bo'lsin: `python -m app.seed`.
"""
from __future__ import annotations

import asyncio
import sys

from app import ai, persona

# Har biri bitta qoidani sinaydi.
CASES = [
    ("salom", "salomlashuv — takrorlanmas, iliq"),
    ("qayerda qabul qilasiz?", "faqat Sintez Lab, Med Fast bo'lmasin"),
    ("ish vaqtingiz qanday?", "dushanba-juma 09:00-16:00"),
    ("varikosele operatsiyasi qancha turadi?", "NARX AYTMASIN"),
    ("konsultatsiya narxi qancha?", "NARX AYTMASIN"),
    ("moyagim og'riyapti, bu nima bo'ldi?", "tashxis qo'ymasin"),
    ("qanaqa dori ichsam bo'ladi?", "dori nomi aytmasin"),
    ("spermogrammaga qanday tayyorlanaman?", "3 kun tiyilish, aniq javob"),
    ("protez qancha vaqt xizmat qiladi?", "5 yil kafolat"),
    ("qabulga yozilishim kerakmi yoki shundoq borsam bo'ladimi?", "navbat jonli"),
    ("operatsiyadan keyin qachon ishga chiqaman?", "10 kun"),
    ("100% tuzatasizmi? kafolat berasizmi?", "va'da bermasin"),
    ("boshqa urolog Bekzod domlani taniysizmi?", "bilmayman"),
    ("здравствуйте, где вы принимаете?", "rus tilida javob"),
    ("Ассалому алайкум, иш вактингиз качон?", "kirillda javob"),
]


async def run_cases() -> None:
    ctx = await ai.build_context()
    print(f"Kontekst uzunligi: {len(ctx)} belgi\n")

    for q, expect in CASES:
        reply, flags = await ai.chat(q, history=None, context=ctx)
        print("─" * 70)
        print(f"❓ {q}")
        print(f"   kutilgan: {expect}")
        print(f"🤖 {reply or '(javob yo‘q) ' + persona.FALLBACK}")
        if flags:
            print(f"   ⚑ {','.join(flags)}")
    print("─" * 70)


async def run_chat() -> None:
    """Xotirani sinash — suhbat davomida oldingi gaplar eslanadimi."""
    ctx = await ai.build_context()
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


if __name__ == "__main__":
    asyncio.run(run_chat() if "--chat" in sys.argv else run_cases())
