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


def appointment_summary(name: str, phone: str, clinic: str, service: str, when: str) -> str:
    return (
        f"📝 <b>Arizangizni tasdiqlang:</b>\n\n"
        f"👤 Ism: {escape(name)}\n"
        f"📱 Telefon: {escape(phone)}\n"
        f"🏥 Klinika: {escape(clinic)}\n"
        f"🩺 Xizmat: {escape(service)}\n"
        f"🕐 Qulay vaqt: {escape(when)}"
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
    "🤖 <b>AI-konsultant tayyorlanmoqda</b>\n\n"
    "Bu bo'lim tez orada ishga tushadi — sun'iy intellekt savolingizga bir zumda "
    "javob beradi.\n\n"
    "Hozircha:\n"
    "• 📅 «Qabulga yozilish» orqali ariza qoldiring;\n"
    "• 📞 +998 90 008 38 78 raqamiga qo'ng'iroq qiling;\n"
    "• ✈️ yoki shifokorga Telegram orqali yozing."
)

ASK_PLACEHOLDER = (
    "✅ Murojaatingiz qabul qilindi va shifokorga yuborildi.\n\n"
    "🤖 Tez orada bu bo'limga <b>AI-konsultant</b> ulanadi — u savolingizga bir zumda "
    "dastlabki javob beradi. Hozircha shifokor yoki uning yordamchisi siz bilan bog'lanadi.\n\n"
    "Shoshilinch holatlarda: 📞 +998 90 008 38 78"
)
