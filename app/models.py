"""Ma'lumotlar bazasi modellari.

Kontent jadvallari (services, methods, clinics, results, faq, advantages, doctor)
bot va Mini App uchun yagona manba — ikkalasi ham shu yerdan o'qiydi.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Doctor(Base):
    """Shifokor profili — bitta yozuv."""

    __tablename__ = "doctor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(160))
    short_name: Mapped[str] = mapped_column(String(80))
    specialty: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(80))
    experience: Mapped[str] = mapped_column(String(40))
    bio: Mapped[str] = mapped_column(Text)
    photo: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(40))
    email: Mapped[str] = mapped_column(String(120), default="")
    telegram: Mapped[str] = mapped_column(String(120), default="")
    instagram: Mapped[str] = mapped_column(String(200), default="")
    youtube: Mapped[str] = mapped_column(String(200), default="")
    website: Mapped[str] = mapped_column(String(200), default="")
    work_hours: Mapped[str] = mapped_column(String(160), default="")


class Service(Base):
    """Xizmatlar — saytdagi «Xizmatlar» bo'limi."""

    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    icon: Mapped[str] = mapped_column(String(8), default="🩺")
    title: Mapped[str] = mapped_column(String(160))
    short: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Method(Base):
    """Jarrohlik usullari — saytdagi «Usullar» bo'limi."""

    __tablename__ = "methods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    icon: Mapped[str] = mapped_column(String(8), default="🔬")
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0)


class Advantage(Base):
    """«Nega aynan men?» bo'limi."""

    __tablename__ = "advantages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    icon: Mapped[str] = mapped_column(String(8), default="✅")
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0)


class Clinic(Base):
    """Qabul joylari."""

    __tablename__ = "clinics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    address: Mapped[str] = mapped_column(String(255))
    landmark: Mapped[str] = mapped_column(String(255), default="")
    map_url: Mapped[str] = mapped_column(String(300), default="")
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)
    photo: Mapped[str] = mapped_column(String(255), default="")
    work_hours: Mapped[str] = mapped_column(String(160), default="")
    position: Mapped[int] = mapped_column(Integer, default=0)


class Result(Base):
    """Natijalar — YouTube videolar."""

    __tablename__ = "results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    youtube_id: Mapped[str] = mapped_column(String(40))
    position: Mapped[int] = mapped_column(Integer, default=0)

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.youtube_id}"

    @property
    def thumb(self) -> str:
        return f"https://img.youtube.com/vi/{self.youtube_id}/hqdefault.jpg"


class Faq(Base):
    """Savol-javob."""

    __tablename__ = "faq"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(String(255))
    answer: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0)


class User(Base):
    """Botga kirgan foydalanuvchilar."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str] = mapped_column(String(64), default="")
    first_name: Mapped[str] = mapped_column(String(120), default="")
    last_name: Mapped[str] = mapped_column(String(120), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    source: Mapped[str] = mapped_column(String(20), default="bot")  # bot | webapp
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    appointments: Mapped[list["Appointment"]] = relationship(back_populates="user")


class Appointment(Base):
    """Qabulga yozilish arizalari — bot ham, Mini App ham shu yerga yozadi."""

    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    tg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    full_name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(40))
    clinic_id: Mapped[int | None] = mapped_column(ForeignKey("clinics.id"), nullable=True)
    service_id: Mapped[int | None] = mapped_column(ForeignKey("services.id"), nullable=True)
    # Kalendardan tanlangan aniq sana va vaqt
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    preferred_time: Mapped[str] = mapped_column(String(120), default="")  # o'qishga qulay ko'rinish
    comment: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="new")  # new|confirmed|done|cancelled
    source: Mapped[str] = mapped_column(String(20), default="bot")  # bot | webapp
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped[User | None] = relationship(back_populates="appointments")
    clinic: Mapped[Clinic | None] = relationship()
    service: Mapped[Service | None] = relationship()


class ChatMessage(Base):
    """«Jonli murojaat» suhbati — AI ning xotirasi.

    Har xabar (bemorniki ham, AI niki ham) shu yerga yoziladi. Keyingi javobda
    oxirgi bir nechtasi modelga kontekst sifatida beriladi. Suhbat botda ham,
    Mini App'da ham bitta `tg_id` bo'yicha davom etadi.

    Suhbat yakunlanganda qatorlar **o'chirilmaydi** — `archived_at` to'ldiriladi.
    Arxivlangan xabar AI kontekstiga tushmaydi, lekin bazada qoladi: bular
    o'qitishning asosiy manbai (`scripts/export_chats.py`).
    """

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    role: Mapped[str] = mapped_column(String(10))  # user | model
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="bot")  # bot | webapp
    # Qoidalar ishga tushgan bo'lsa shu yerda: narx, eski_klinika, shoshilinch…
    flags: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # NULL = suhbat davom etyapti; to'ldirilgan = yakunlangan, arxivda
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SupportThread(Base):
    """Operator guruhidagi mavzu (topic) — har bemorga bittadan.

    Nima uchun kerak: Telegramda bir vaqtda bir necha bemor yozadi. Agar
    hammasi bitta oqimga tushsa, jonli admin kim nima yozganini ajrata
    olmaydi. Shuning uchun guruh «forum» rejimida ishlaydi va har bemorning
    suhbati o'z mavzusida jonli ko'chib boradi. Admin o'sha mavzuga yozsa —
    javob bemorga ketadi.

    `mode`:
      • `ai`    — odatdagi holat, javobni AI yozadi;
      • `human` — suhbatga odam aralashdi, AI jim turadi.

    AI `HUMAN_PAUSE_MINUTES` (odatda 60 daqiqa) o'tgach o'zi qaytadi:
    shifokorning qarori — admin unutib qo'ysa ham bemor javobsiz qolmasin.
    Odam yozgan xabarlar `chat_messages` ga `role='model'` bo'lib tushadi,
    shuning uchun qaytgan AI ular bilan tanishgan holda davom etadi.
    """

    __tablename__ = "support_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    topic_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mode: Mapped[str] = mapped_column(String(10), default="ai")  # ai | human
    # Oxirgi marta odam javob bergan payt — pauza shundan hisoblanadi.
    human_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    title: Mapped[str] = mapped_column(String(160), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Consultation(Base):
    """Murojaatlar / savollar.

    Hozircha faqat saqlanadi va adminga yuboriladi. Keyinchalik shu jadvalga
    AI operator javob yozadi (`ai_answer`, `answered_at`).
    """

    __tablename__ = "consultations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    tg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    message: Mapped[str] = mapped_column(Text)
    ai_answer: Mapped[str] = mapped_column(Text, default="")
    answered_by: Mapped[str] = mapped_column(String(20), default="")  # ai | doctor
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|answered|closed
    source: Mapped[str] = mapped_column(String(20), default="bot")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped[User | None] = relationship()
