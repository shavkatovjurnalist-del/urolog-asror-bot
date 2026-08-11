"""Bot matnlari va formatlash yordamchilari (HTML parse_mode)."""
from __future__ import annotations

from html import escape


def welcome(doctor) -> str:
    return (
        f"👋 Assalomu alaykum!\n\n"
        f"<b>{escape(doctor.short_name)}</b> — {escape(doctor.specialty)}\n"
        f"🏅 {escape(doctor.category)} · 🕐 Tajriba: {escape(doctor.experience)}\n"
        f"📍 Samarqand shahri\n\n"
        f"Bu yerda siz shifokorning xizmatlari, jarrohlik usullari, qabul joylari va "
        f"natijalari bilan tanishishingiz, hamda <b>qabulga yozilishingiz</b> mumkin.\n\n"
        f"🌐 Saytning to'liq versiyasini <b>Telegramdan chiqmasdan</b> ochish uchun "
        f"«{escape('🌐 Sayt (Mini App)')}» tugmasini bosing."
    )


def doctor_card(doctor) -> str:
    return (
        f"👨‍⚕️ <b>{escape(doctor.full_name)}</b>\n"
        f"{escape(doctor.specialty)} · {escape(doctor.category)}\n"
        f"🕐 Tajriba: {escape(doctor.experience)}\n\n"
        f"{escape(doctor.bio)}\n\n"
        f"🗓 <b>Qabul kunlari:</b> {escape(doctor.work_hours)}\n"
        f"📞 {escape(doctor.phone)}"
    )


def service_card(service) -> str:
    return (
        f"{service.icon} <b>{escape(service.title)}</b>\n\n"
        f"{escape(service.description)}\n\n"
        f"<i>Aniq tashxis va davolash rejasi ko'rikdan so'ng belgilanadi.</i>"
    )


def method_card(method) -> str:
    return f"{method.icon} <b>{escape(method.title)}</b>\n\n{escape(method.description)}"


def clinic_card(clinic) -> str:
    parts = [f"🏥 <b>{escape(clinic.name)}</b>", f"📍 {escape(clinic.address)}"]
    if clinic.landmark:
        parts.append(f"🧭 {escape(clinic.landmark)}")
    if clinic.work_hours:
        parts.append(f"🕐 {escape(clinic.work_hours)}")
    return "\n".join(parts)


def faq_text(items) -> str:
    out = ["❓ <b>Ko'p beriladigan savollar</b>\n"]
    for i, f in enumerate(items, 1):
        out.append(f"<b>{i}. {escape(f.question)}</b>\n{escape(f.answer)}\n")
    return "\n".join(out)


def advantages_text(items) -> str:
    out = ["⭐️ <b>Nega aynan Dr. Asror To'rayev?</b>\n"]
    for a in items:
        out.append(f"{a.icon} <b>{escape(a.title)}</b>\n{escape(a.description)}\n")
    return "\n".join(out)


def contact_text(doctor) -> str:
    return (
        f"📞 <b>Aloqa</b>\n\n"
        f"Bemorlar oldindan yozilish asosida qabul qilinadi.\n\n"
        f"🗓 <b>Ish kunlari:</b> {escape(doctor.work_hours)}\n"
        f"📱 <b>Telefon:</b> {escape(doctor.phone)}\n"
        f"✉️ <b>Email:</b> {escape(doctor.email)}\n"
        f"🌐 <b>Sayt:</b> {escape(doctor.website)}\n\n"
        f"📍 Samarqand shahri"
    )


PICK_DATE = (
    "5/5 — 📅 <b>Qabul kunini tanlang</b>\n\n"
    "Onlayn yozilish <b>ertangi kundan</b> boshlab ochiq.\n"
    "Shanba va yakshanba — dam olish kunlari (kalendarda «·» bilan belgilangan)."
)


def pick_time(day_text: str) -> str:
    return (
        f"📅 <b>{escape(day_text)}</b>\n\n"
        f"🕐 Endi qulay soatni tanlang.\n"
        f"<i>Qabul 09:00 – 16:00, 13:00 – 14:00 tushlik.</i>"
    )


def appointment_summary(name: str, phone: str, clinic: str, service: str, when: str) -> str:
    return (
        f"📝 <b>Arizangizni tasdiqlang:</b>\n\n"
        f"👤 Ism: {escape(name)}\n"
        f"📱 Telefon: {escape(phone)}\n"
        f"🏥 Klinika: {escape(clinic)}\n"
        f"🩺 Xizmat: {escape(service)}\n"
        f"🕐 Qabul vaqti: {escape(when)}"
    )


def appointment_accepted(appt_id: int, when: str) -> str:
    return (
        f"✅ <b>Arizangiz qabul qilindi!</b>\n\n"
        f"🔢 <b>Murojaat raqami: №{appt_id}</b>\n"
        f"🕐 Tanlangan vaqt: {escape(when or 'kelishilgan holda')}\n\n"
        f"⏳ <b>Iltimos, javobni kuting.</b>\n"
        f"Shifokor arizangizni ko'rib chiqib tasdiqlaydi — natija shu yerga xabar "
        f"bo'lib keladi.\n\n"
        f"Shoshilinch holatlarda: 📞 +998 90 008 38 78"
    )


def appointment_confirmed(appt_id: int, when: str, clinic: str) -> str:
    return (
        f"✅ <b>Murojaatingiz qabul qilindi!</b>\n\n"
        f"🔢 Murojaat raqami: <b>№{appt_id}</b>\n"
        f"🕐 Qabul vaqti: <b>{escape(when or 'kelishilgan holda')}</b>\n"
        f"🏥 Manzil: {escape(clinic)}\n\n"
        f"🙏 <b>Qabulga kechikmay keling.</b>\n"
        f"Iltimos, belgilangan vaqtdan 10 daqiqa oldin yetib boring."
    )


def appointment_rejected(appt_id: int, when: str) -> str:
    return (
        f"❌ <b>Afsuski, bu vaqt band ekan</b>\n\n"
        f"🔢 Murojaat raqami: №{appt_id}\n"
        f"🕐 So'ralgan vaqt: {escape(when or '—')}\n\n"
        f"Iltimos, <b>boshqa kun va vaqtni tanlab qayta ariza qoldiring</b> — "
        f"«📅 Qabulga yozilish» tugmasini bosing.\n\n"
        f"Savollar bo'lsa: 📞 +998 90 008 38 78"
    )


def admin_appointment(appt, clinic: str, service: str, username: str) -> str:
    return (
        f"🔔 <b>Yangi ariza #{appt.id}</b>\n\n"
        f"👤 {escape(appt.full_name)}\n"
        f"📱 {escape(appt.phone)}\n"
        f"🏥 {escape(clinic)}\n"
        f"🩺 {escape(service)}\n"
        f"🕐 {escape(appt.preferred_time or '—')}\n"
        f"💬 {escape(appt.comment or '—')}\n\n"
        f"📲 Manba: {escape(appt.source)} · {escape(username or '—')}"
    )


def admin_consultation(c, username: str) -> str:
    return (
        f"💬 <b>Yangi murojaat #{c.id}</b>\n\n"
        f"{escape(c.message)}\n\n"
        f"📲 Manba: {escape(c.source)} · {escape(username or '—')}"
    )


DISCLAIMER = (
    "ℹ️ <i>Botdagi ma'lumotlar tanishtiruv xarakteriga ega va shifokor ko'rigi o'rnini "
    "bosmaydi. Aniq tashxis uchun qabulga yoziling.</i>"
)

ASK_DISABLED = (
    "🤖 <b>Jonli murojaat tayyorlanmoqda</b>\n\n"
    "Bu bo'lim tez orada ishga tushadi — shifokorning admini savolingizga bir zumda "
    "javob beradi.\n\n"
    "Hozircha:\n"
    "• 📅 «Qabulga yozilish» orqali ariza qoldiring;\n"
    "• 📞 +998 90 008 38 78 raqamiga qo'ng'iroq qiling;\n"
    "• ✈️ yoki shifokorga Telegram orqali yozing."
)
