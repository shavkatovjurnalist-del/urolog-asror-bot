"""Loyiha sozlamalari — barchasi .env dan o'qiladi."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _ids(raw: str) -> list[int]:
    return [int(x) for x in raw.replace(" ", "").split(",") if x]


BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_IDS: list[int] = _ids(os.getenv("ADMIN_IDS", ""))

# Hisobot boti (@ai_humoyunbot) — arizalar va kunlik xulosalar shu yerga tushadi.
# Faqat sendMessage ishlatiladi; uning webhook'iga tegilmaydi.
REPORT_BOT_TOKEN: str = os.getenv("REPORT_BOT_TOKEN", "")
REPORT_CHAT_IDS: list[int] = _ids(os.getenv("REPORT_CHAT_IDS", ""))

# «Murojaat» bo'limi. AI agent ulanmaguncha o'chirib turiladi.
ASK_ENABLED: bool = os.getenv("ASK_ENABLED", "false").lower() == "true"

# ── Jonli operator guruhi ──────────────────────────────────────────────
# Har bemorning suhbati shu guruhda alohida mavzuda (topic) jonli ko'chib
# boradi; admin o'sha mavzuga yozsa javob bemorga ketadi.
#
# Sozlash: guruh oching → Sozlamalar → «Mavzular» (Topics) yoqing →
# botni admin qiling («Mavzularni boshqarish» huquqi bilan) → guruhda
# `/id` yozing va chiqqan raqamni shu yerga qo'ying.
#
# Bo'sh qoldirilsa guruh butunlay o'chiq bo'ladi va bot avvalgidek ishlaydi
# — hech narsa buzilmaydi.
SUPPORT_GROUP_ID: int = int(os.getenv("SUPPORT_GROUP_ID", "0") or 0)

# Odam suhbatga aralashgach AI qancha vaqt jim turadi (daqiqa).
# Shifokorning qarori: bir soat. Undan keyin AI odam yozganlarni o'qib,
# suhbatni shunga mos davom ettiradi.
HUMAN_PAUSE_MINUTES: int = int(os.getenv("HUMAN_PAUSE_MINUTES", "60"))

BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "secret")
WEBHOOK_PATH: str = f"/webhook/{WEBHOOK_SECRET}"
PORT: int = int(os.getenv("PORT", "8000"))

WEBAPP_URL: str = f"{BASE_URL}/app/"

_raw_db = os.getenv("DATABASE_URL", "").strip()
if not _raw_db:
    DATABASE_URL = f"sqlite+aiosqlite:///{BASE_DIR / 'urolog.db'}"
else:
    # Neon/Render `postgresql://` beradi — asyncpg drayveriga o'girib olamiz
    if _raw_db.startswith("postgres://"):
        _raw_db = _raw_db.replace("postgres://", "postgresql://", 1)
    if _raw_db.startswith("postgresql://"):
        _raw_db = _raw_db.replace("postgresql://", "postgresql+asyncpg://", 1)
    # asyncpg `sslmode` / `channel_binding` parametrlarini tushunmaydi —
    # TLS `app/db.py` da connect_args orqali beriladi.
    if "?" in _raw_db:
        base, _, query = _raw_db.partition("?")
        keep = [
            p for p in query.split("&")
            if p and not p.startswith(("sslmode=", "channel_binding=", "options="))
        ]
        _raw_db = base + ("?" + "&".join(keep) if keep else "")
    DATABASE_URL = _raw_db

# AI-konsultant (Google Gemini). Kalit: aistudio.google.com
AI_ENABLED: bool = os.getenv("AI_ENABLED", "false").lower() == "true"
AI_API_KEY: str = os.getenv("AI_API_KEY", "")
AI_MODEL: str = os.getenv("AI_MODEL", "gemini-3.5-flash-lite")

WEBAPP_DIR = BASE_DIR / "webapp"
