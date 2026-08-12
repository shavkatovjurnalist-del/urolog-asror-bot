"""Bot mantiqi — barcha handlerlar."""
from __future__ import annotations

import logging
from datetime import date, datetime
from datetime import time as dtime
from html import escape

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

from app import ai, persona, repo, report, support
from app.bot import calendar as cal
from app.bot import keyboards as kb
from app.bot import texts as t
from app.config import ADMIN_IDS, ASK_ENABLED, BASE_DIR, SUPPORT_GROUP_ID
from app.db import session_scope

log = logging.getLogger(__name__)
router = Router()

# Jonli suhbat alohida routerda va Dispatcher'ga BIRINCHI ulanadi
# (`app/bot/instance.py`). Sabab: suhbat davomida bemor yozgan har qanday matn
# AI ga borishi kerak — menyu tugmalarining matnini yozib yuborsa ham.
live_router = Router()

# Operator guruhidan keladigan xabarlar — eng birinchi tekshiriladi, aks holda
# ular oddiy bemor xabari deb qabul qilinardi.
support_router = Router()

PHOTO_DOCTOR = BASE_DIR / "webapp" / "assets" / "asror.webp"


# ─────────────────────────── FSM holatlari ───────────────────────────
class Booking(StatesGroup):
    name = State()
    phone = State()
    clinic = State()
    service = State()
    day = State()
    time = State()
    confirm = State()


class Live(StatesGroup):
    """«Jonli murojaat» — AI bilan davomli suhbat."""

    chatting = State()


# ─────────────────────────── Yordamchilar ───────────────────────────
async def notify_admins(bot, text: str, markup=None) -> None:
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, reply_markup=markup)
        except Exception as e:  # admin botni bloklagan bo'lishi mumkin
            log.warning("Adminga (%s) yuborilmadi: %s", admin_id, e)


def _uname(user) -> str:
    return f"@{user.username}" if getattr(user, "username", None) else f"id{user.id}"


async def _leave_live_if_any(message: Message, state: FSMContext) -> None:
    """/start yoki /menu bosilsa jonli suhbat tartibli yopiladi (tarix shifokorga ketadi)."""
    if await state.get_state() == Live.chatting.state:
        await _finish_live(message, state, by_user=False)


# ─────────────────────────── /start ───────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await _leave_live_if_any(message, state)
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
    await _leave_live_if_any(message, state)
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
        "📅 <b>Qabulga yozilish</b>\n\n1/5 — Ism-familiyangizni yozing:",
        reply_markup=kb.cancel_kb(),
    )


@router.callback_query(F.data == "book:start")
async def book_start_cb(cq: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Booking.name)
    await cq.message.answer(
        "📅 <b>Qabulga yozilish</b>\n\n1/5 — Ism-familiyangizni yozing:",
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
        "📅 <b>Qabulga yozilish</b>\n\n1/5 — Ism-familiyangizni yozing:",
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
        "2/5 — Telefon raqamingizni yuboring yoki yozing (masalan +998901234567):",
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
    # Qabul faqat bitta klinikada bo'lsa — tanlash so'ralmaydi.
    if len(clinics) == 1:
        await state.update_data(clinic_id=clinics[0].id)
        await _ask_service(message, state)
        return
    rows = [[InlineKeyboardButton(text=f"🏥 {c.name}", callback_data=f"bkc:{c.id}")] for c in clinics]
    rows.append([InlineKeyboardButton(text="🤷 Farqi yo'q", callback_data="bkc:0")])
    await state.set_state(Booking.clinic)
    await message.answer(
        "3/5 — Qaysi klinikada qabul qilinishni xohlaysiz?",
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
    # «Konsultatsiya» — ro'yxatning eng tepasida
    rows = [[InlineKeyboardButton(text="💬 Konsultatsiya (umumiy maslahat)",
                                  callback_data="bks:0")]]
    rows += [[InlineKeyboardButton(text=f"{sv.icon} {sv.title}", callback_data=f"bks:{sv.id}")]
             for sv in services]
    await state.set_state(Booking.service)
    await message.answer(
        "4/5 — Qaysi masala bo'yicha murojaat qilyapsiz?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(Booking.service, F.data.startswith("bks:"))
async def book_service(cq: CallbackQuery, state: FSMContext) -> None:
    sid = int(cq.data.split(":")[1])
    await state.update_data(service_id=sid or None)
    await state.set_state(Booking.day)
    await cq.answer()
    await cq.message.answer(t.PICK_DATE, reply_markup=cal.start_calendar_kb())


# ─── 5/5: sana ───
@router.callback_query(F.data == "cal:skip")
async def cal_skip(cq: CallbackQuery) -> None:
    await cq.answer()


@router.callback_query(F.data == "cal:cancel")
async def cal_cancel(cq: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cq.message.edit_text("Ariza bekor qilindi.")
    await cq.message.answer("Asosiy menyu:", reply_markup=kb.main_menu())
    await cq.answer()


@router.callback_query(Booking.day, F.data.startswith("cal:nav:"))
async def cal_nav(cq: CallbackQuery) -> None:
    year, month = (int(x) for x in cq.data.split(":")[2].split("-"))
    await cq.message.edit_reply_markup(reply_markup=cal.calendar_kb(year, month))
    await cq.answer()


@router.callback_query(Booking.day, F.data.startswith("cal:day:"))
async def cal_day(cq: CallbackQuery, state: FSMContext) -> None:
    picked = date.fromisoformat(cq.data.split(":")[2])
    if not cal.is_selectable(picked):
        await cq.answer("Bu kunni tanlab bo'lmaydi", show_alert=True)
        return
    await state.update_data(day=picked.isoformat())
    await state.set_state(Booking.time)
    await cq.message.edit_text(t.pick_time(cal.fmt_date(picked)), reply_markup=cal.time_kb(picked))
    await cq.answer()


# ─── 5/5: vaqt ───
@router.callback_query(Booking.time, F.data == "tm:back")
async def time_back(cq: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    picked = date.fromisoformat(data["day"])
    await state.set_state(Booking.day)
    await cq.message.edit_text(t.PICK_DATE, reply_markup=cal.calendar_kb(picked.year, picked.month))
    await cq.answer()


@router.callback_query(Booking.time, F.data.startswith("tm:set:"))
async def time_set(cq: CallbackQuery, state: FSMContext) -> None:
    slot = cq.data.split(":", 2)[2]
    data = await state.get_data()
    picked = date.fromisoformat(data["day"])
    hour, minute = (int(x) for x in slot.split(":"))
    await state.update_data(
        scheduled_at=datetime.combine(picked, dtime(hour, minute)).isoformat(),
        preferred_time=f"{cal.fmt_date(picked)}, soat {slot}",
    )
    await cq.answer()
    await _confirm(cq.message, state, edit=True)


async def _confirm(message: Message, state: FSMContext, edit: bool = False) -> None:
    data = await state.get_data()
    async with session_scope() as s:
        clinic = await repo.get_clinic(s, data["clinic_id"]) if data.get("clinic_id") else None
        service = await repo.get_service(s, data["service_id"]) if data.get("service_id") else None
    await state.set_state(Booking.confirm)
    text = t.appointment_summary(
        data["full_name"],
        data["phone"],
        clinic.name if clinic else "Farqi yo'q",
        service.title if service else "Konsultatsiya (umumiy maslahat)",
        data.get("preferred_time", "—"),
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="bk:ok"),
        InlineKeyboardButton(text="❌ Bekor", callback_data="bk:no"),
    ]])
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


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
            scheduled_at=(
                datetime.fromisoformat(data["scheduled_at"]) if data.get("scheduled_at") else None
            ),
            preferred_time=data.get("preferred_time", ""),
            source="bot",
        )
        clinic = await repo.get_clinic(s, appt.clinic_id) if appt.clinic_id else None
        service = await repo.get_service(s, appt.service_id) if appt.service_id else None
        clinic_name = clinic.name if clinic else "Farqi yo'q"
        service_name = service.title if service else "Konsultatsiya (umumiy maslahat)"
        admin_text = t.admin_appointment(appt, clinic_name, service_name, _uname(cq.from_user))

    await state.clear()
    await cq.message.edit_text(t.appointment_accepted(appt.id, appt.preferred_time))
    await cq.message.answer("Asosiy menyu:", reply_markup=kb.main_menu())
    await cq.answer("Qabul qilindi ✅")
    await notify_admins(cq.bot, admin_text, kb.admin_appointment_kb(appt.id))
    await report.new_appointment(appt, clinic_name, service_name, _uname(cq.from_user))


# ─────────────────────────── Jonli murojaat (AI suhbati) ───────────────────────────
@router.message(F.text.in_({kb.BTN_LIVE, kb.BTN_ASK}))
async def live_start(message: Message, state: FSMContext) -> None:
    """Suhbatni boshlaydi: AI o'zi salom berib, masalani so'raydi."""
    if not ASK_ENABLED:
        await message.answer(t.ASK_DISABLED, reply_markup=kb.main_menu())
        return

    await state.clear()
    async with session_scope() as s:
        await repo.upsert_user(s, message.from_user)
        # Yangi suhbat — eski tarix aralashmasin.
        await repo.archive_chat_history(s, message.from_user.id)
        await repo.add_chat_message(
            s, message.from_user.id, "model", persona.GREETING, source="bot"
        )

    await state.set_state(Live.chatting)
    await state.update_data(started=datetime.utcnow().isoformat(), reported=False)
    await message.answer(persona.GREETING, reply_markup=kb.live_chat_kb())


# ─── Suhbat davomidagi handlerlar (live_router — birinchi tekshiriladi) ───
@live_router.message(Live.chatting, Command("start", "menu", "help"))
async def live_command(message: Message, state: FSMContext) -> None:
    """Suhbat ichida /start yoki /menu — suhbat tartibli yopilib, menyu chiqadi."""
    await _finish_live(message, state, by_user=False)
    await message.answer(
        "📋 Suhbat yakunlandi. Asosiy menyu:", reply_markup=kb.main_menu()
    )


@live_router.message(Live.chatting, F.text == kb.BTN_END_CHAT)
async def live_end(message: Message, state: FSMContext) -> None:
    await _finish_live(message, state, by_user=True)


@live_router.message(Live.chatting, F.text == kb.BTN_BOOK)
async def live_to_booking(message: Message, state: FSMContext) -> None:
    """Suhbatdan qabulga yozilishga o'tish — suhbat yozuvi yo'qolmasin."""
    await _finish_live(message, state, by_user=False)
    await book_start(message, state)


# Ovozli xabarning yuqori chegarasi. Gemini ga base64 qilib yuboriladi,
# uzun yozuv so'rovni og'irlashtiradi va javobni kechiktiradi.
MAX_VOICE_BYTES = 8 * 1024 * 1024

RASM_JAVOBI = (
    "Rasmni oldim, Asror Abbosovichga yetkazaman. Faqat shuni aytib qo'yay — "
    "shifokor ko'pincha masofadan turib tashxis qo'ymaydi, aniq javob uchun "
    "ko'rikdan o'tish kerak bo'ladi."
)

OVOZ_TUSHUNARSIZ = (
    "Kechirasiz, ovozli xabaringizni aniq eshitolmadim. Iltimos, "
    "savolingizni matn qilib yozib yuboring — shunda aniq javob beraman."
)


@live_router.message(Live.chatting, F.voice | F.audio | F.video_note)
async def live_voice(message: Message, state: FSMContext) -> None:
    """Ovozli xabar: matnga o'girilib, oddiy savol kabi javob beriladi.

    O'girib bo'lmasa — bemordan yozib yuborish so'raladi va suhbat jonli
    adminga uzatiladi (shifokorning qarori: sifatli o'girilganda admin
    bezovta qilinmaydi).
    """
    media = message.voice or message.audio or message.video_note
    await support.relay_user_media(
        message.bot, message.from_user, message, "ovozli xabar yubordi"
    )

    text = None
    if media and (media.file_size or 0) <= MAX_VOICE_BYTES:
        try:
            buf = await message.bot.download(media.file_id)
            mime = getattr(media, "mime_type", None) or "audio/ogg"
            await message.bot.send_chat_action(message.chat.id, "typing")
            text = await ai.transcribe(buf.read(), mime)
        except Exception as e:
            log.warning("Ovozli xabar yuklanmadi (%s): %s", message.from_user.id, e)

    if not text:
        async with session_scope() as s:
            await repo.add_chat_message(
                s, message.from_user.id, "user", "[ovozli xabar — o'girib bo'lmadi]",
                flags="ovoz_noaniq",
            )
            await repo.add_chat_message(
                s, message.from_user.id, "model", OVOZ_TUSHUNARSIZ, flags="ovoz_noaniq"
            )
        await message.answer(OVOZ_TUSHUNARSIZ, reply_markup=kb.live_chat_kb())
        await _escalate(message, state, "🎤 Ovozli xabar tushunilmadi", "[ovozli xabar]")
        return

    # Matnga o'girildi — bundan keyin oddiy savol kabi ishlanadi.
    await support.notify(
        message.bot, message.from_user.id, f"🎤 <i>matnga o'girildi:</i> {escape(text)}"
    )
    await _handle_patient_text(message, state, text, relayed=True)


@live_router.message(Live.chatting, F.photo | F.document)
async def live_photo(message: Message, state: FSMContext) -> None:
    """Rasm va hujjat. Shifokorning qarori: rasm O'QILMAYDI, u odamga uzatiladi."""
    note = "[bemor rasm/hujjat yubordi]"
    await support.relay_user_media(
        message.bot, message.from_user, message, "rasm/hujjat yubordi"
    )
    async with session_scope() as s:
        await repo.add_chat_message(s, message.from_user.id, "user", note, flags="media")
        await repo.add_chat_message(s, message.from_user.id, "model", RASM_JAVOBI)
    await message.answer(RASM_JAVOBI, reply_markup=kb.live_chat_kb())
    await _escalate(message, state, "🖼 Rasm / hujjat yuborildi", note)


@live_router.message(Live.chatting, F.text)
async def live_message(message: Message, state: FSMContext) -> None:
    await _handle_patient_text(message, state, message.text.strip())


async def _handle_patient_text(
    message: Message, state: FSMContext, text: str, relayed: bool = False
) -> None:
    """Bemorning savoliga javob — matn ham, ovozdan o'girilgani ham shu yerdan.

    `relayed=True` — xabar operator guruhiga allaqachon ko'chirilgan
    (ovozli xabar o'z fayli bilan tushgan), ikkinchi marta ko'chirilmaydi.
    """
    tg_id = message.from_user.id

    # 0. Bemor yozgani operator guruhidagi o'z mavzusiga ko'chadi — jonli
    #    admin suhbatni real vaqtda kuzatib turadi.
    if not relayed:
        await support.relay_user_text(message.bot, message.from_user, text)

    # 1. Shoshilinch holat — modelga umuman bormaydi. Odam suhbatda bo'lsa
    #    ham shu javob beriladi: kechiktirib bo'lmaydigan holat.
    if ai.is_urgent(text):
        async with session_scope() as s:
            await repo.add_chat_message(s, tg_id, "user", text, flags="shoshilinch")
            await repo.add_chat_message(s, tg_id, "model", persona.URGENT, flags="shoshilinch")
        await message.answer(persona.URGENT, reply_markup=kb.live_chat_kb())
        await _escalate(message, state, "🚨 SHOSHILINCH", text)
        return

    # 2. AI butunlay to'xtatilganmi (operator botidagi kod 404).
    #    Xabar guruhga tushaveradi — javobni odam yozadi, bemor
    #    e'tibordan chetda qolmaydi.
    if await repo.ai_paused():
        async with session_scope() as s:
            await repo.add_chat_message(s, tg_id, "user", text, flags="ai_toxtatilgan")
        await support.notify(
            message.bot, tg_id,
            "⛔️ <i>AI to'xtatilgan (kod 404) — javobni shu yerdan yozing.</i>",
        )
        return

    # 3. Suhbatga odam aralashgan yoki javobi kutilayotgan bo'lsa AI jim
    #    turadi. Ikkala muddat ham o'zi tugaydi (`support.is_paused`).
    if await support.is_paused(tg_id):
        async with session_scope() as s:
            await repo.add_chat_message(s, tg_id, "user", text, flags="odam_rejimi")
        return

    # 4. Bemor odamni so'radi — AI o'zi to'xtaydigan yagona holat.
    #    Modelga ishonib bo'lmaydi: u «hozir xabar beraman» deb yozardi-yu,
    #    hech qanday signal ketmasdi (Bobur sinovda topdi).
    if ai.asks_human(text):
        async with session_scope() as s:
            await repo.add_chat_message(s, tg_id, "user", text, flags="odam_soradi")
            await repo.add_chat_message(
                s, tg_id, "model", persona.HANDOFF, flags="odam_soradi"
            )
        await message.answer(persona.HANDOFF, reply_markup=kb.live_chat_kb())
        await support.relay_ai(message.bot, tg_id, persona.HANDOFF)
        await _escalate(message, state, "Bemor boshqa admin so'radi", text, wait=True)
        return

    # 5. Suhbat tarixi bilan modelga
    async with session_scope() as s:
        history = await repo.get_chat_history(s, tg_id, limit=ai.HISTORY_LIMIT)
        await repo.add_chat_message(s, tg_id, "user", text)

    await message.bot.send_chat_action(message.chat.id, "typing")
    reply, flags = await ai.chat(text, history=history)

    if not reply:
        log.warning("AI javob bermadi (%s): %s", tg_id, ",".join(flags))
        reply = persona.FALLBACK
        flags = flags + ["fallback"]

    if ai.asks_price(text):
        flags = flags + ["narx"]

    async with session_scope() as s:
        await repo.add_chat_message(s, tg_id, "model", reply, flags=",".join(flags))

    await message.answer(reply, reply_markup=kb.live_chat_kb())
    await support.relay_ai(message.bot, tg_id, reply)

    # 6. Manzil so'ralgan bo'lsa — xaritadagi nuqta. Shifokorning talabi:
    #    manzil matn bilan tasvirlanmasin, bemor joylashuvni bosib ko'rsin.
    if ai.asks_location(text):
        await _send_clinic_location(message)

    # 7. Boshqa admin ko'rishi kerak bo'lgan holatlar.
    #    Oddiy suhbat uchun signal YUBORILMAYDI — u guruhdagi mavzuda
    #    baribir jonli ko'rinib turadi. Ilgari har yangi bemor signal
    #    bo'lib ketardi va bu shovqin edi.
    if "fallback" in flags:
        # AI javob berolmadi — bemor kutadi, javobni odam yozadi.
        await _escalate(message, state, "AI javob berolmadi", text, wait=True)
    elif ai.is_offtopic(reply):
        # Savol mavzudan tashqari — bemor odam so'ramagan, lekin javobni
        # odam berishi kerak.
        await _escalate(message, state, "Mavzudan tashqari savol", text, wait=True)
    elif ai.is_unclear(reply):
        # AI tushunmadi, lekin bemorga «aniqroq yozing» deb javob berdi —
        # suhbat davom etadi, admin faqat xabardor bo'ladi.
        await _escalate(message, state, "Noaniq xabar — AI tushunmadi", text)


async def _send_clinic_location(message: Message) -> None:
    """Klinika joylashuvi: xarita nuqtasi va tagida bir og'iz izoh."""
    async with session_scope() as s:
        clinics = await repo.get_clinics(s)
    for c in clinics:
        if not (c.latitude and c.longitude):
            continue
        await message.answer_location(latitude=c.latitude, longitude=c.longitude)
        note = f"📍 {c.name}, {c.address}"
        if c.landmark:
            note += f" ({c.landmark})"
        await message.answer(note, reply_markup=kb.live_chat_kb())
        break  # qabul bitta joyda — birinchi klinika yetarli


async def _finish_live(message: Message, state: FSMContext, by_user: bool) -> None:
    """Suhbatni yopadi: tarixni shifokorga yuboradi va arxivga o'tkazadi.

    Arxivlangan xabarlar bazada qoladi (o'chirilmaydi) — ular AI ni o'qitish
    manbai: `python -m scripts.export_chats`.
    """
    tg_id = message.from_user.id
    async with session_scope() as s:
        history = await repo.get_chat_history(s, tg_id, limit=60)
        await repo.archive_chat_history(s, tg_id)
    await state.clear()

    # Suhbat yozuvi operator botiga YUBORILMAYDI: u guruhdagi mavzuda
    # jonli ko'rinib turadi va yakunda takrorlash faqat shovqin bo'lardi.
    # Guruh sozlanmagan bo'lsagina yozuv yuboriladi — aks holda suhbat
    # hech qayerda ko'rinmay qolardi.
    if not support.enabled() and any(m["role"] == "user" for m in history):
        await report.live_chat_transcript(history, _uname(message.from_user), tg_id)

    if by_user:
        await message.answer(
            "Suhbat yakunlandi. Kerak bo'lsa istalgan vaqtda yana yozavering — "
            "menyudan «💬 Jonli murojaat» tugmasini bosing.",
            reply_markup=kb.main_menu(),
        )


async def _record_consultation(message: Message, state: FSMContext, text: str) -> None:
    """Murojaatni bazaga bir marta yozadi (statistika uchun).

    Xabar YUBORMAYDI: signal faqat `_escalate` orqali ketadi.
    """
    data = await state.get_data()
    if data.get("reported"):
        return
    await state.update_data(reported=True)
    async with session_scope() as s:
        user = await repo.upsert_user(s, message.from_user)
        await repo.create_consultation(
            s, user_id=user.id, tg_id=message.from_user.id, message=text,
            source="bot-live",
        )


async def _escalate(
    message: Message, state: FSMContext, reason: str, text: str, wait: bool = False
) -> None:
    """Boshqa adminga signal — tugmali xabar bilan.

    `wait=True` — AI javob bermay javob kutadi (bemorga «ulayapman» deb
    aytilgan). Admin `WAIT_MINUTES` ichida tanlamasa AI o'zi davom etadi.
    `wait=False` — suhbat davom etaveradi, admin faqat xabardor bo'ladi.
    """
    tg_id = message.from_user.id
    await _record_consultation(message, state, text)

    if wait:
        await support.set_mode(tg_id, "waiting")

    async with session_scope() as s:
        history = await repo.get_chat_history(s, tg_id, limit=8)
        th = await support.get_thread(s, tg_id)

    # Guruhdagi mavzuga ham belgi — admin qaysi suhbat ekanini darhol ko'radi.
    await support.notify(message.bot, tg_id, f"⚠️ <b>{escape(reason)}</b>")
    await report.escalation(
        tg_id=tg_id,
        who=support.title_of(message.from_user),
        reason=reason,
        history=history,
        topic_id=th.topic_id if th else None,
        waiting=wait,
    )


# ═══════════════════ Operator guruhi (boshqa admin) ═══════════════════
# Guruhda bot faqat o'z mavzularini kuzatadi. Admin mavzuga yozgan matn
# to'g'ridan-to'g'ri bemorga ketadi va AI `HUMAN_PAUSE_MINUTES` ga jim
# bo'ladi.
#
# ⚠️ BotFather'da bu bot uchun «Group Privacy» O'CHIRILGAN bo'lishi shart
# (/setprivacy → Disable), aks holda bot guruhdagi oddiy matnni umuman
# ko'rmaydi — faqat buyruqlarni ko'radi.
_SUPPORT_CHAT = F.chat.id == SUPPORT_GROUP_ID


async def _thread_user(topic_id: int | None) -> int | None:
    if not topic_id:
        return None
    async with session_scope() as s:
        th = await support.thread_by_topic(s, topic_id)
    return th.tg_id if th else None


@support_router.message(_SUPPORT_CHAT, Command("ai"))
async def support_resume_ai(message: Message) -> None:
    """AI ni darhol qaytaradi (pauzani kutmasdan)."""
    tg_id = await _thread_user(message.message_thread_id)
    if tg_id is None:
        await message.reply("Bu mavzu bemorga bog'lanmagan.")
        return
    await support.set_mode(tg_id, "ai")
    await message.reply("🤖 AI qaytdi — keyingi xabarga u javob beradi.")


@support_router.message(_SUPPORT_CHAT, Command("odam", "stop"))
async def support_hold_ai(message: Message) -> None:
    """AI ni to'xtatib turadi — javobni faqat odam yozadi."""
    tg_id = await _thread_user(message.message_thread_id)
    if tg_id is None:
        await message.reply("Bu mavzu bemorga bog'lanmagan.")
        return
    await support.set_mode(tg_id, "human")
    await message.reply(
        f"✋ AI to'xtatildi. {support.HUMAN_PAUSE_MINUTES} daqiqadan keyin "
        f"o'zi qaytadi yoki /ai bosing."
    )


@support_router.message(_SUPPORT_CHAT, F.text | F.photo | F.voice | F.document)
async def support_reply(message: Message) -> None:
    """Admin mavzuga yozdi — xabar bemorga ketadi, AI pauzaga o'tadi."""
    tg_id = await _thread_user(message.message_thread_id)
    if tg_id is None:
        # Mavzular yoqilmagan bo'lsa xabar qaysi bemorga tegishli ekani
        # noma'lum bo'ladi va admin javobi jimgina yo'qolib ketardi —
        # admin buni sezmasdi. Shuning uchun aniq aytamiz.
        if not message.chat.is_forum:
            await message.reply(
                "⚠️ Guruhda «Mavzular» (Topics) yoqilmagan — bu xabar bemorga "
                "yetib bormadi.\n\nGuruh sozlamalari → «Mavzular» ni yoqing, "
                "so'ng botga «Mavzularni boshqarish» huquqini bering."
            )
        return  # xizmat mavzusi yoki bog'lanmagan xabar

    try:
        if message.text:
            await message.bot.send_message(tg_id, message.text)
        else:
            await message.bot.copy_message(
                chat_id=tg_id, from_chat_id=message.chat.id, message_id=message.message_id
            )
    except Exception as e:
        log.warning("Bemorga (%s) yuborilmadi: %s", tg_id, e)
        await message.reply(f"❌ Bemorga yetib bormadi: {e}")
        return

    # Odam yozgani AI ning xotirasiga `model` roli bilan tushadi — pauza
    # tugagach AI aynan shu gaplarni o'qib, suhbatni shunga mos davom
    # ettiradi va aytilganini takrorlamaydi.
    body = message.text or f"[admin {message.content_type} yubordi]"
    async with session_scope() as s:
        await repo.add_chat_message(s, tg_id, "model", body, flags="human")
    await support.set_mode(tg_id, "human")


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
    """Shaxsiy ID va (guruhda ishlatilsa) guruh ID si.

    Guruh ID si operator guruhini sozlash uchun kerak: uni `.env` dagi
    `SUPPORT_GROUP_ID` ga yoziladi.
    """
    lines = [f"👤 Sizning Telegram ID: <code>{message.from_user.id}</code>"]
    if message.chat.type in {"group", "supergroup"}:
        lines.append(f"💬 Guruh ID: <code>{message.chat.id}</code>")
        lines.append(
            f"🧵 Mavzular (Topics): "
            f"{'yoqilgan ✅' if message.chat.is_forum else 'yoqilmagan ❌'}"
        )
    await message.answer("\n".join(lines))


# ─────────────────────────── Eskirgan tugmalar ───────────────────────────
@router.callback_query(F.data.startswith(("cal:", "tm:", "bk:", "bks:", "bkc:")))
async def stale_callback(cq: CallbackQuery, state: FSMContext) -> None:
    """Servis qayta ishga tushsa FSM holati yo'qoladi — foydalanuvchini chalkashtirmaymiz."""
    await state.clear()
    await cq.answer("Ariza jarayoni eskirgan", show_alert=False)
    await cq.message.answer(
        "⚠️ Ariza jarayoni uzilib qoldi.\n\n"
        "Iltimos, «📅 Qabulga yozilish» tugmasini bosib qaytadan boshlang.",
        reply_markup=kb.main_menu(),
    )


# ─────────────────────────── Boshqa har qanday matn ───────────────────────────
@router.message(F.text)
async def fallback(message: Message, state: FSMContext) -> None:
    if await state.get_state():
        return

    # FSM xotirada saqlanadi (MemoryStorage), servis esa uxlab-uyg'onadi va
    # qayta ishga tushadi — o'shanda `Live.chatting` yo'qoladi. Bemor uchun
    # esa suhbat davom etayotgan bo'ladi. Bazada yakunlanmagan suhbat bo'lsa
    # holatni tiklab, xabarni AI ga uzatamiz: bemor «Menyudan tanlang» degan
    # javob olib chalkashmaydi va suhbat tarixi ham saqlanib qoladi.
    if ASK_ENABLED:
        async with session_scope() as s:
            open_chat = await repo.has_open_chat(s, message.from_user.id)
        if open_chat:
            await state.set_state(Live.chatting)
            await state.update_data(
                started=datetime.utcnow().isoformat(), reported=True
            )
            await live_message(message, state)
            return

    hint = (
        "Savolingiz bo'lsa — «💬 Jonli murojaat» tugmasini bosing, "
        "shifokorning admini bilan yozishasiz."
        if ASK_ENABLED
        else "Qabulga yozilish uchun «📅 Qabulga yozilish» tugmasini bosing."
    )
    await message.answer(f"Menyudan kerakli bo'limni tanlang 👇\n\n{hint}", reply_markup=kb.main_menu())
