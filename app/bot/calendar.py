"""Qabul uchun inline kalendar va vaqt tanlash.

Qoidalar:
  • faqat ertangi kundan boshlab (bugun va o'tgan kunlar yopiq);
  • shanba va yakshanba — dam olish, tanlab bo'lmaydi;
  • soat 09:00 – 16:00, 13:00 – 14:00 tushlik (yopiq).

Vaqtlar shifokor anketasidan (2026-08-11). Oxirgi qabul 15:00 da boshlanadi.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# O'zbekiston vaqti (UTC+5)
TZ_OFFSET = timedelta(hours=5)

MONTHS = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
          "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]
MONTHS_GEN = ["yanvar", "fevral", "mart", "aprel", "may", "iyun",
              "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]
WEEK_SHORT = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]
WEEK_FULL = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]

# Ish soatlari — tushlik (13:00-14:00) chiqarib tashlangan
TIME_SLOTS = ["09:00", "10:00", "11:00", "12:00", "14:00", "15:00"]

MAX_DAYS_AHEAD = 60
WEEKEND = {5, 6}  # shanba, yakshanba


def today_local() -> date:
    return (datetime.utcnow() + TZ_OFFSET).date()


def min_date() -> date:
    """Eng erta tanlash mumkin bo'lgan kun — ertaga."""
    return today_local() + timedelta(days=1)


def max_date() -> date:
    return today_local() + timedelta(days=MAX_DAYS_AHEAD)


def is_selectable(d: date) -> bool:
    return min_date() <= d <= max_date() and d.weekday() not in WEEKEND


def fmt_date(d: date) -> str:
    return f"{d.day}-{MONTHS_GEN[d.month - 1]}, {WEEK_FULL[d.weekday()]}"


def calendar_kb(year: int, month: int) -> InlineKeyboardMarkup:
    """Bir oylik kalendar."""
    first = date(year, month, 1)
    rows: list[list[InlineKeyboardButton]] = []

    # Sarlavha va navigatsiya
    prev_m = first - timedelta(days=1)
    next_m = (first.replace(day=28) + timedelta(days=7)).replace(day=1)

    nav = []
    nav.append(
        InlineKeyboardButton(text="‹", callback_data=f"cal:nav:{prev_m.year}-{prev_m.month}")
        if date(prev_m.year, prev_m.month, 1) >= date(min_date().year, min_date().month, 1)
        else InlineKeyboardButton(text=" ", callback_data="cal:skip")
    )
    nav.append(InlineKeyboardButton(text=f"{MONTHS[month - 1]} {year}", callback_data="cal:skip"))
    nav.append(
        InlineKeyboardButton(text="›", callback_data=f"cal:nav:{next_m.year}-{next_m.month}")
        if next_m <= max_date()
        else InlineKeyboardButton(text=" ", callback_data="cal:skip")
    )
    rows.append(nav)

    rows.append([InlineKeyboardButton(text=w, callback_data="cal:skip") for w in WEEK_SHORT])

    # Kunlar
    week: list[InlineKeyboardButton] = []
    for _ in range(first.weekday()):
        week.append(InlineKeyboardButton(text=" ", callback_data="cal:skip"))

    day = first
    while day.month == month:
        if is_selectable(day):
            week.append(InlineKeyboardButton(
                text=str(day.day), callback_data=f"cal:day:{day.isoformat()}"
            ))
        else:
            week.append(InlineKeyboardButton(text="·", callback_data="cal:skip"))

        if len(week) == 7:
            rows.append(week)
            week = []
        day += timedelta(days=1)

    if week:
        while len(week) < 7:
            week.append(InlineKeyboardButton(text=" ", callback_data="cal:skip"))
        rows.append(week)

    rows.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cal:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def start_calendar_kb() -> InlineKeyboardMarkup:
    d = min_date()
    return calendar_kb(d.year, d.month)


def time_kb(d: date) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    buf: list[InlineKeyboardButton] = []
    for slot in TIME_SLOTS:
        buf.append(InlineKeyboardButton(text=f"🕐 {slot}", callback_data=f"tm:set:{slot}"))
        if len(buf) == 3:
            rows.append(buf)
            buf = []
    if buf:
        rows.append(buf)
    rows.append([
        InlineKeyboardButton(text="⬅️ Sanani o'zgartirish", callback_data="tm:back"),
        InlineKeyboardButton(text="❌ Bekor", callback_data="cal:cancel"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)
