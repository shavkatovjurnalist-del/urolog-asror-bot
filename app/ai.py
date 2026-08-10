"""AI operator uchun bo'sh joy (placeholder).

Hozircha AI ulanmagan. Kelajakda `answer()` funksiyasi ichiga model chaqiruvi
qo'yiladi va `AI_ENABLED=true` qilinadi — qolgan kod o'zgarmaydi.

Ulash tartibi:
  1. `.env` da AI_ENABLED=true va AI_API_KEY=... ni to'ldiring;
  2. quyidagi `answer()` ichida modelga so'rov yuboring;
  3. natija avtomatik ravishda `consultations.ai_answer` ga yoziladi va
     foydalanuvchiga (bot yoki Mini App orqali) qaytariladi.
"""
from __future__ import annotations

from app.config import AI_ENABLED

SYSTEM_PROMPT = (
    "Sen urolog-androlog Dr. Asror To'rayevning yordamchi AI-konsultantisan. "
    "O'zbek tilida, qisqa va tushunarli javob ber. Tashxis qo'yma va dori buyurma — "
    "faqat umumiy ma'lumot ber va shifokor qabuliga yozilishni taklif qil."
)


async def answer(question: str, context: str = "") -> str | None:
    """Foydalanuvchi savoliga AI javobi. AI ulanmagan bo'lsa None qaytaradi."""
    if not AI_ENABLED:
        return None

    # TODO: AI operator shu yerga ulanadi.
    # Masalan:
    #   from anthropic import AsyncAnthropic
    #   client = AsyncAnthropic(api_key=AI_API_KEY)
    #   resp = await client.messages.create(
    #       model="claude-sonnet-5", max_tokens=600,
    #       system=SYSTEM_PROMPT + context,
    #       messages=[{"role": "user", "content": question}],
    #   )
    #   return resp.content[0].text
    return None
