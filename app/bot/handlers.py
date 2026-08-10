"""Bot mantiqi — barcha handlerlar."""
from __future__ import annotations

import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app import repo
from app.ai import answer as ai_answer
from app.bot import keyboards as kb
from app.bot import texts as t
from app.config import ADMIN_IDS, BASE_DIR
from app.db import session_scope
from app.models import Consultation

log = logging.getLogger(__name__)
router = Router()

PHOTO_DOCTOR = BASE_DIR / "webapp" / "assets" / "asror.webp"


# ─────────────────────────── FSM holatlari ───────────────────────────
class Booking(StatesGroup):
    name = State()
    phone = State()
    clinic = State()
    service = State()
    when = State()
    confirm = State()


class Ask(StatesGroup):
    message = State()


# ─────────────────────────── Yordamchilar ───────────────────────────
async def notify_admins(bot, text: str, markup=None) -> None:
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, reply_markup=markup)
        except Exception as e:  # admin botni bloklagan bo'lishi mumkin
            log.warning("Adminga (%s) yuborilmadi: %s", admin_id, e)


def _uname(user) -> str:
    return f"@{user.username}" if getattr(user, "username", None) else f"id{user.id}"


# ─────────────────────────── /start ───────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    async with session_scope() as s:
        await repo.upsert_user(s, message.from_user)
        doctor = await repo.get_doctor(s)

    caption = t.welcome(doctor)
    if PHOTO_DOCTOR.exists():
        await message.answer_photo(
            FSInputFile(PHOTO_DOCTOR), caption=caption, reply_markup=kb.main_menu()
        )
    else:
        await message.answer(caption, reply_markup=kb.main_menu())


@router.message(Command("menu"))
@router.message(Command("help"))
async def cmd_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "📋 Asosiy menyu. Kerakli bo'limni tanlang:", reply_markup=kb.main_menu()
    )


@router.message(F.text == "❌ Bekor qilish")
async def cancel_any(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=kb.main_menu())


# ─────────────────────────── Xizmatlar ───────────────────────────
@router.message(F.text == kb.BTN_SERVICES)
async def services_list(message: Message) -> None:
    async with session_scope() as s:
        items = await repo.get_services(s)
    await message.answer(
        "🩺 <b>Xizmatlar</b>\n\nBatafsil ma'lumot uchun xizmatni tanlang:",
        reply_markup=kb.list_kb(items, "svc"),
    )


@router.callback_query(F.data == "svc:list")
async def services_list_cb(cq: CallbackQuery) -> None:
    async with session_scope() as s:
        items = await repo.get_services(s)
    await cq.message.edit_text(
        "🩺 <b>Xizmatlar</b>\n\nBatafsil ma'lumot uchun xizmatni tanlang:",
        reply_markup=kb.list_kb(items, "svc"),
    )
    await cq.answer()


@router.callback_query(F.data.startswith("svc:"))
async def service_detail(cq: CallbackQuery) -> None:
    sid = int(cq.data.split(":")[1])
    async with session_scope() as s:
        item = await repo.get_service(s, sid)
    if not item:
        await cq.answer("Topilmadi", show_alert=True)
        return
    await cq.message.edit_text(t.service_card(item), reply_markup=kb.detail_kb("svc:list"))
    await cq.answer()


# ─────────────────────────── Usullar ───────────────────────────
@router.message(F.text == kb.BTN_METHODS)
async def methods_list(message: Message) -> None:
    async with session_scope() as s:
        items = await repo.get_methods(s)
    await message.answer(
        "🔬 <b>Urologiyada jarrohlik usullari</b>\n\n"
        "Zamonaviy texnologiyalar bilan minimal invaziv va xavfsiz davolash:",
        reply_markup=kb.list_kb(items, "mtd"),
    )


@router.callback_query(F.data == "mtd:list")
async def methods_list_cb(cq: CallbackQuery) -> None:
    async with session_scope() as s:
        items = await repo.get_methods(s)
    await cq.message.edit_text(
        "🔬 <b>Urologiyada jarrohlik usullari</b>\n\nUsulni tanlang:",
        reply_markup=kb.list_kb(items, "mtd"),
    )
    await cq.answer()


@router.callback_query(F.data.startswith("mtd:"))
async def method_detail(cq: CallbackQuery) -> None:
    mid = int(cq.data.split(":")[1])
    async with session_scope() as s:
        item = await repo.get_method(s, mid)
    if not item:
        await cq.answer("Topilmadi", show_alert=True)
        return
    await cq.message.edit_text(t.method_card(item), reply_markup=kb.detail_kb("mtd:list"))
    await cq.answer()


# ─────────────────────────── Qabul joylari ───────────────────────────
@router.message(F.text == kb.BTN_CLINICS)
async def clinics_list(message: Message) -> None:
    async with session_scope() as s:
        items = await repo.get_clinics(s)
    for c in items:
        photo = BASE_DIR / "webapp" / "assets" / c.photo.split("/")[-1]
        if photo.exists():
            await message.answer_photo(
                FSInputFile(photo), caption=t.clinic_card(c), reply_markup=kb.clinic_kb(c)
            )
        else:
            await message.answer(t.clinic_card(c), reply_markup=kb.clinic_kb(c))
        if c.latitude and c.longitude:
            await message.answer_location(latitude=c.latitude, longitude=c.longitude)


@router.callback_query(F.data == "clinics")
async def clinics_cb(cq: CallbackQuery) -> None:
    await clinics_list(cq.message)
    await cq.answer()


# ─────────────────────────── Natijalar ───────────────────────────
@router.message(F.text == kb.BTN_RESULTS)
async def results_list(message: Message) -> None:
    async with session_scope() as s:
        items = await repo.get_results(s)
        doctor = await repo.get_doctor(s)
    rows = [
        [InlineKeyboardButton(text=f"▶️ {r.title}", url=r.url)] for r in items
    ]
    rows.append([InlineKeyboardButton(text="📺 YouTube kanal", url=doctor.youtube)])
    await message.answer(
        "🎬 <b>Haqiqiy natijalar</b>\n\n"
        "Bemorlarning davolanish jarayoni va muvaffaqiyatli natijalari bilan "
        "videolarda tanishing:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


# ─────────────────────────── Shifokor haqida ───────────────────────────
@router.message(F.text == kb.BTN_DOCTOR)
async def doctor_about(message: Message) -> None:
    async with session_scope() as s:
        doctor = await repo.get_doctor(s)
        advantages = await repo.get_advantages(s)
    if PHOTO_DOCTOR.exists():
        await message.answer_photo(FSInputFile(PHOTO_DOCTOR), caption=t.doctor_card(doctor))
    else:
        await message.answer(t.doctor_card(doctor))
    await message.answer(t.advantages_text(advantages), reply_markup=kb.contact_kb(doctor))


# ─────────────────────────── Savol-javob ───────────────────────────
@router.message(F.text == kb.BTN_FAQ)
async def faq(message: Message) -> None:
    async with session_scope() as s:
        items = await repo.get_faq(s)
    await message.answer(t.faq_text(items) + "\n" + t.DISCLAIMER)


# ─────────────────────────── Aloqa ───────────────────────────
@router.message(F.text == kb.BTN_CONTACT)
async def contact(message: Message) -> None:
    async with session_scope() as s:
        doctor = await repo.get_doctor(s)
        clinics = await repo.get_clinics(s)
    text = t.contact_text(doctor) + "\n\n" + "\n\n".join(t.clinic_card(c) for c in clinics)
    await message.answer(text, reply_markup=kb.contact_kb(doctor))


# ─────────────────────────── Qabulga yozilish (FSM) ───────────────────────────
@router.message(F.text == kb.BTN_BOOK)
async def book_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Booking.name)
    await message.answer(
        "📅 <b>Qabulga yozilish</b>\n\n1/4 — Ism-familiyangizni yozing:",
        reply_markup=kb.cancel_kb(),
    )


@router.callback_query(F.data == "book:start")
async def book_start_cb(cq: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Booking.name)
    await cq.message.answer(
        "📅 <b>Qabulga yozilish</b>\n\n1/4 — Ism-familiyangizni yozing:",
        reply_markup=kb.cancel_kb(),
    )
    await cq.answer()


@router.callback_query(F.data.startswith("book:clinic:"))
async def book_start_with_clinic(cq: CallbackQuery, state: FSMContext) -> None:
    clinic_id = int(cq.data.split(":")[2])
    await state.clear()
    await state.update_data(clinic_id=clinic_id)
    await state.set_state(Booking.name)
    await cq.message.answer(
        "📅 <b>Qabulga yozilish</b>\n\n1/4 — Ism-familiyangizni yozing:",
        reply_markup=kb.cancel_kb(),
    )
    await cq.answer()


@router.message(Booking.name, F.text)
async def book_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if len(name) < 3:
        await message.answer("Iltimos, to'liq ism-familiyangizni yozing.")
        return
    await state.update_data(full_name=name)
    await state.set_state(Booking.phone)
    await message.answer(
        "2/4 — Telefon raqamingizni yuboring yoki yozing (masalan +998901234567):",
        reply_markup=kb.phone_kb(),
    )


@router.message(Booking.phone, F.contact)
async def book_phone_contact(message: Message, state: FSMContext) -> None:
    await _book_after_phone(message, state, message.contact.phone_number)


@router.message(Booking.phone, F.text)
async def book_phone_text(message: Message, state: FSMContext) -> None:
    phone = message.text.strip()
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) < 9:
        await message.answer("Raqam noto'g'ri ko'rinadi. Masalan: +998901234567")
        return
    await _book_after_phone(message, state, phone)


async def _book_after_phone(message: Message, state: FSMContext, phone: str) -> None:
    await state.update_data(phone=phone)
    data = await state.get_data()
    if data.get("clinic_id"):
        await _ask_service(message, state)
        return
    async with session_scope() as s:
        clinics = await repo.get_clinics(s)
    rows = [[InlineKeyboardButton(text=f"🏥 {c.name}", callback_data=f"bkc:{c.id}")] for c in clinics]
    rows.append([InlineKeyboardButton(text="🤷 Farqi yo'q", callback_data="bkc:0")])
    await state.set_state(Booking.clinic)
    await message.answer(
        "3/4 — Qaysi klinikada qabul qilinishni xohlaysiz?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(Booking.clinic, F.data.startswith("bkc:"))
async def book_clinic(cq: CallbackQuery, state: FSMContext) -> None:
    cid = int(cq.data.split(":")[1])
    await state.update_data(clinic_id=cid or None)
    await cq.answer()
    await _ask_service(cq.message, state)


async def _ask_service(message: Message, state: FSMContext) -> None:
    async with session_scope() as s:
        services = await repo.get_services(s)
    rows = [[InlineKeyboardButton(text=f"{sv.icon} {sv.title}", callback_data=f"bks:{sv.id}")]
            for sv in services]
    rows.append([InlineKeyboardButton(text="❔ Bilmayman / maslahat kerak", callback_data="bks:0")])
    await state.set_state(Booking.service)
    await message.answer(
        "4/4 — Qaysi masala bo'yicha murojaat qilyapsiz?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(Booking.service, F.data.startswith("bks:"))
async def book_service(cq: CallbackQuery, state: FSMContext) -> None:
    sid = int(cq.data.split(":")[1])
    await state.update_data(service_id=sid or None)
    await state.set_state(Booking.when)
    await cq.answer()
    await cq.message.answer(
        "🕐 Sizga qulay kun va vaqtni yozing (masalan: «ertaga tushdan keyin»).\n"
        "Yoki «⏭ O'tkazib yuborish» tugmasini bosing.",
        reply_markup=kb.skip_kb("bkw:skip"),
    )


@router.callback_query(Booking.when, F.data == "bkw:skip")
async def book_when_skip(cq: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(preferred_time="Farqi yo'q")
    await cq.answer()
    await _confirm(cq.message, state)


@router.message(Booking.when, F.text)
async def book_when(message: Message, state: FSMContext) -> None:
    await state.update_data(preferred_time=message.text.strip())
    await _confirm(message, state)


async def _confirm(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    async with session_scope() as s:
        clinic = await repo.get_clinic(s, data["clinic_id"]) if data.get("clinic_id") else None
        service = await repo.get_service(s, data["service_id"]) if data.get("service_id") else None
    await state.set_state(Booking.confirm)
    await message.answer(
        t.appointment_summary(
            data["full_name"],
            data["phone"],
            clinic.name if clinic else "Farqi yo'q",
            service.title if service else "Umumiy maslahat",
            data.get("preferred_time", "—"),
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="bk:ok"),
            InlineKeyboardButton(text="❌ Bekor", callback_data="bk:no"),
        ]]),
    )


@router.callback_query(Booking.confirm, F.data == "bk:no")
async def book_cancel(cq: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cq.message.edit_text("Ariza bekor qilindi.")
    await cq.message.answer("Asosiy menyu:", reply_markup=kb.main_menu())
    await cq.answer()


@router.callback_query(Booking.confirm, F.data == "bk:ok")
async def book_save(cq: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    async with session_scope() as s:
        user = await repo.upsert_user(s, cq.from_user)
        if data.get("phone"):
            user.phone = data["phone"]
            await s.commit()
        appt = await repo.create_appointment(
            s,
            user_id=user.id,
            tg_id=cq.from_user.id,
            full_name=data["full_name"],
            phone=data["phone"],
            clinic_id=data.get("clinic_id"),
            service_id=data.get("service_id"),
            preferred_time=data.get("preferred_time", ""),
            source="bot",
        )
        clinic = await repo.get_clinic(s, appt.clinic_id) if appt.clinic_id else None
        service = await repo.get_service(s, appt.service_id) if appt.service_id else None
        admin_text = t.admin_appointment(
            appt,
            clinic.name if clinic else "Farqi yo'q",
            service.title if service else "Umumiy maslahat",
            _uname(cq.from_user),
        )

    await state.clear()
    await cq.message.edit_text(
        f"✅ <b>Arizangiz qabul qilindi!</b> (№{appt.id})\n\n"
        "Shifokor yordamchisi tez orada siz bilan bog'lanadi.\n"
        "Shoshilinch holatlarda: 📞 +998 90 008 38 78"
    )
    await cq.message.answer("Asosiy menyu:", reply_markup=kb.main_menu())
    await cq.answer("Qabul qilindi ✅")
    await notify_admins(cq.bot, admin_text, kb.admin_appointment_kb(appt.id))


# ─────────────────────────── Murojaat / Savol (AI joyi) ───────────────────────────
@router.message(F.text == kb.BTN_ASK)
async def ask_start(message: Message, state: FSMContext) -> None:
    await state.set_state(Ask.message)
    await message.answer(
        "💬 <b>Murojaat / Savol</b>\n\n"
        "Savolingizni yoki shikoyatingizni batafsil yozing. Shifokor javob beradi.\n\n"
        "🤖 <i>Yaqin orada bu bo'limga AI-konsultant ulanadi.</i>",
        reply_markup=kb.cancel_kb(),
    )


@router.message(Ask.message, F.text)
async def ask_save(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if len(text) < 5:
        await message.answer("Iltimos, savolingizni biroz batafsilroq yozing.")
        return

    async with session_scope() as s:
        user = await repo.upsert_user(s, message.from_user)
        c = await repo.create_consultation(
            s, user_id=user.id, tg_id=message.from_user.id, message=text, source="bot"
        )
        admin_text = t.admin_consultation(c, _uname(message.from_user))

    await state.clear()

    # AI ulanganda shu joyda javob qaytadi; hozircha None keladi.
    reply = await ai_answer(text)
    if reply:
        async with session_scope() as s:
            obj = await s.get(Consultation, c.id)
            obj.ai_answer = reply
            obj.answered_by = "ai"
            obj.answered_at = datetime.utcnow()
            obj.status = "answered"
            await s.commit()
        await message.answer(f"🤖 {reply}\n\n{t.DISCLAIMER}", reply_markup=kb.main_menu())
    else:
        await message.answer(t.ASK_PLACEHOLDER, reply_markup=kb.main_menu())

    await notify_admins(message.bot, admin_text)


# ─────────────────────────── Admin ───────────────────────────
@router.callback_query(F.data.startswith("adm:appt:"))
async def admin_appt(cq: CallbackQuery) -> None:
    if cq.from_user.id not in ADMIN_IDS:
        await cq.answer("Ruxsat yo'q", show_alert=True)
        return
    _, _, action, appt_id = cq.data.split(":")
    from app.models import Appointment

    async with session_scope() as s:
        appt = await s.get(Appointment, int(appt_id))
        if not appt:
            await cq.answer("Topilmadi", show_alert=True)
            return
        appt.status = "confirmed" if action == "confirm" else "cancelled"
        await s.commit()
        tg_id = appt.tg_id

    mark = "✅ Tasdiqlandi" if action == "confirm" else "❌ Bekor qilindi"
    await cq.message.edit_text(cq.message.html_text + f"\n\n<b>{mark}</b>")
    await cq.answer(mark)

    if tg_id and action == "confirm":
        try:
            await cq.bot.send_message(
                tg_id,
                "✅ Arizangiz tasdiqlandi! Shifokor yordamchisi qabul vaqtini "
                "aniqlashtirish uchun siz bilan bog'lanadi.",
            )
        except Exception as e:
            log.warning("Bemorga xabar yuborilmadi: %s", e)


@router.message(Command("stats"))
async def stats(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    from sqlalchemy import func, select

    from app.models import Appointment, Consultation as C, User

    async with session_scope() as s:
        users = (await s.execute(select(func.count(User.id)))).scalar()
        appts = (await s.execute(select(func.count(Appointment.id)))).scalar()
        new_appts = (
            await s.execute(select(func.count(Appointment.id)).where(Appointment.status == "new"))
        ).scalar()
        cons = (await s.execute(select(func.count(C.id)))).scalar()
    await message.answer(
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Foydalanuvchilar: {users}\n"
        f"📅 Arizalar: {appts} (yangi: {new_appts})\n"
        f"💬 Murojaatlar: {cons}"
    )


@router.message(Command("id"))
async def whoami(message: Message) -> None:
    await message.answer(f"Sizning Telegram ID: <code>{message.from_user.id}</code>")


# ─────────────────────────── Boshqa har qanday matn ───────────────────────────
@router.message(F.text)
async def fallback(message: Message, state: FSMContext) -> None:
    if await state.get_state():
        return
    await message.answer(
        "Menyudan kerakli bo'limni tanlang 👇\n\n"
        "Savolingiz bo'lsa — «💬 Murojaat / Savol» tugmasini bosing.",
        reply_markup=kb.main_menu(),
    )
