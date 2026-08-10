"""Bot klaviaturalari."""
from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from app.config import ASK_ENABLED, BASE_URL, WEBAPP_URL

# Telegram faqat https manzilli Web App tugmalarini qabul qiladi.
# Lokal sinovda (http://localhost) tugmalar ko'rsatilmaydi.
WEBAPP_ENABLED = BASE_URL.startswith("https://")

# --- Asosiy menyu matnlari (handlerlarda filtr sifatida ishlatiladi) ---
BTN_WEBAPP = "🌐 Sayt (Mini App)"
BTN_SERVICES = "🩺 Xizmatlar"
BTN_METHODS = "🔬 Jarrohlik usullari"
BTN_CLINICS = "📍 Qabul joylari"
BTN_RESULTS = "🎬 Natijalar"
BTN_DOCTOR = "👨‍⚕️ Shifokor haqida"
BTN_FAQ = "❓ Savol-javob"
BTN_BOOK = "📅 Qabulga yozilish"
BTN_ASK = "💬 Murojaat / Savol"
BTN_CONTACT = "📞 Aloqa"


def main_menu() -> ReplyKeyboardMarkup:
    rows = []
    if WEBAPP_ENABLED:
        rows.append([KeyboardButton(text=BTN_WEBAPP, web_app=WebAppInfo(url=WEBAPP_URL))])
    return ReplyKeyboardMarkup(
        keyboard=[
            *rows,
            [KeyboardButton(text=BTN_SERVICES), KeyboardButton(text=BTN_METHODS)],
            [KeyboardButton(text=BTN_CLINICS), KeyboardButton(text=BTN_RESULTS)],
            [KeyboardButton(text=BTN_DOCTOR), KeyboardButton(text=BTN_FAQ)],
            # «Murojaat» AI agent ulangach ochiladi (ASK_ENABLED=true)
            [KeyboardButton(text=BTN_BOOK), KeyboardButton(text=BTN_ASK)]
            if ASK_ENABLED else [KeyboardButton(text=BTN_BOOK)],
            [KeyboardButton(text=BTN_CONTACT)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Menyudan tanlang yoki savolingizni yozing…",
    )


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True,
    )


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Raqamimni yuborish", request_contact=True)],
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
    )


def list_kb(items, prefix: str, back: str = "menu", columns: int = 1) -> InlineKeyboardMarkup:
    """Ro'yxat uchun inline tugmalar: [icon] sarlavha."""
    rows: list[list[InlineKeyboardButton]] = []
    buf: list[InlineKeyboardButton] = []
    for item in items:
        icon = getattr(item, "icon", "") or ""
        title = getattr(item, "title", None) or getattr(item, "name", "")
        buf.append(
            InlineKeyboardButton(
                text=f"{icon} {title}".strip(),
                callback_data=f"{prefix}:{item.id}",
            )
        )
        if len(buf) == columns:
            rows.append(buf)
            buf = []
    if buf:
        rows.append(buf)
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=back)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def detail_kb(back_cb: str, book: bool = True) -> InlineKeyboardMarkup:
    rows = []
    if book:
        rows.append([InlineKeyboardButton(text="📅 Qabulga yozilish", callback_data="book:start")])
    last = [InlineKeyboardButton(text="⬅️ Ro'yxatga qaytish", callback_data=back_cb)]
    if WEBAPP_ENABLED:
        last.append(InlineKeyboardButton(text="🌐 Mini App", web_app=WebAppInfo(url=WEBAPP_URL)))
    rows.append(last)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def contact_kb(doctor) -> InlineKeyboardMarkup:
    # Eslatma: Telegram inline tugmalarda `tel:` havolasini qabul qilmaydi,
    # shuning uchun raqam xabar matnida (bosiladigan holda) beriladi.
    rows = [
        [InlineKeyboardButton(text="✈️ Telegramdan yozish", url=doctor.telegram)],
        [
            InlineKeyboardButton(text="📸 Instagram", url=doctor.instagram),
            InlineKeyboardButton(text="▶️ YouTube", url=doctor.youtube),
        ],
    ]
    if WEBAPP_ENABLED:
        rows.append([InlineKeyboardButton(text="🌐 Mini App", web_app=WebAppInfo(url=WEBAPP_URL))])
    else:
        rows.append([InlineKeyboardButton(text="🌐 Sayt", url=doctor.website)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def clinic_kb(clinic) -> InlineKeyboardMarkup:
    rows = []
    if clinic.map_url:
        rows.append([InlineKeyboardButton(text="🗺 Xaritada ochish", url=clinic.map_url)])
    rows.append([InlineKeyboardButton(text="📅 Shu joyga yozilish", callback_data=f"book:clinic:{clinic.id}")])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="clinics")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def skip_kb(cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data=cb)]]
    )


def admin_appointment_kb(appointment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"adm:appt:confirm:{appointment_id}"),
            InlineKeyboardButton(text="❌ Bekor", callback_data=f"adm:appt:cancel:{appointment_id}"),
        ]]
    )
