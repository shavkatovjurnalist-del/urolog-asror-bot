"""Jonli suhbatlarni ko'rish — AI ni o'qitish uchun asosiy manba.

    .\.venv\Scripts\python.exe -m scripts.export_chats              # oxirgi 7 kun
    .\.venv\Scripts\python.exe -m scripts.export_chats --days 30
    .\.venv\Scripts\python.exe -m scripts.export_chats --flagged    # faqat belgili
    .\.venv\Scripts\python.exe -m scripts.export_chats --out suhbatlar.md

Baza `DATABASE_URL` dan olinadi. Jonli suhbatlarni ko'rish uchun uni
Render'dagi qiymatga qo'ying (yoki `--dsn` bering).

Haftalik tartib:
  1. shu skriptni ishga tushiring;
  2. noto'g'ri yoki g'aliz javoblarni belgilang;
  3. har birini uch turga ajrating:
       fakt yetishmaydi   -> app/knowledge.py
       xulq noto'g'ri     -> app/persona.py
       noto'g'ri yo'nalish -> kalit so'z / chegara
  4. `python -m scripts.ai_test` bilan qayta tekshiring.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import ChatMessage


def _fmt(dt: datetime | None) -> str:
    return dt.strftime("%d.%m %H:%M") if dt else "—"


async def collect(days: int, flagged_only: bool, dsn: str | None) -> str:
    if dsn:
        os.environ["DATABASE_URL"] = dsn
    # config/db import qilishdan OLDIN DATABASE_URL qo'yilishi kerak
    from app.db import SessionLocal

    since = datetime.utcnow() - timedelta(days=days)
    async with SessionLocal() as s:
        q = (
            select(ChatMessage)
            .where(ChatMessage.created_at >= since)
            .order_by(ChatMessage.id)
        )
        rows = list((await s.execute(q)).scalars())

    if not rows:
        return f"Oxirgi {days} kunda suhbat yo'q."

    # Bitta odamning bir nechta suhbati bo'lishi mumkin — arxivlangan vaqti
    # bo'yicha ajratamiz (bir suhbatning barcha xabarlari bir vaqtda arxivlanadi).
    sessions: dict[tuple[int, str], list[ChatMessage]] = defaultdict(list)
    for m in rows:
        key = (m.tg_id, m.archived_at.isoformat() if m.archived_at else "davom etyapti")
        sessions[key].append(m)

    out: list[str] = [
        f"# Jonli suhbatlar — oxirgi {days} kun",
        f"\nJami {len(sessions)} ta suhbat, {len(rows)} ta xabar."
        f" Yaratildi: {_fmt(datetime.utcnow())} (UTC)\n",
    ]

    shown = 0
    for (tg_id, ended), msgs in sorted(sessions.items(), key=lambda kv: kv[1][0].id):
        flags = {f for m in msgs for f in (m.flags or "").split(",") if f}
        if flagged_only and not flags:
            continue
        shown += 1
        head = f"\n## Suhbat #{shown} · `{tg_id}` · {_fmt(msgs[0].created_at)}"
        if ended == "davom etyapti":
            head += " · ⏳ DAVOM ETYAPTI"
        if flags:
            head += f" · ⚑ {', '.join(sorted(flags))}"
        out.append(head)
        out.append(f"Manba: {msgs[0].source} · {len(msgs)} xabar\n")
        for m in msgs:
            who = "**Bemor:**" if m.role == "user" else "**AI:**"
            mark = f"  `⚑{m.flags}`" if m.flags else ""
            out.append(f"{who} {m.text}{mark}\n")
        out.append("> Baho: ✅ / ❌ ____________  Sabab: fakt / xulq / yo'nalish\n")

    if shown == 0:
        return "Belgili (flagged) suhbat topilmadi."

    # Qaysi qoidalar eng ko'p ishga tushgani — nimani tuzatish kerakligini ko'rsatadi
    counter: dict[str, int] = defaultdict(int)
    for m in rows:
        for f in (m.flags or "").split(","):
            if f:
                counter[f] += 1
    if counter:
        out.append("\n---\n\n## Qoidalar statistikasi\n")
        for f, n in sorted(counter.items(), key=lambda kv: -kv[1]):
            out.append(f"- `{f}` — {n} marta")

    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--flagged", action="store_true", help="faqat qoidalar ishlagan suhbatlar")
    ap.add_argument("--out", help="natijani faylga yozish (.md)")
    ap.add_argument("--dsn", help="boshqa baza (masalan Render'dagi Neon)")
    a = ap.parse_args()

    text = asyncio.run(collect(a.days, a.flagged, a.dsn))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"✅ Yozildi: {a.out} ({len(text)} belgi)")
    else:
        print(text)


if __name__ == "__main__":
    main()
