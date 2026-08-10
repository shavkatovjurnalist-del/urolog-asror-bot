# Dr. Asror To'rayev — Telegram bot + Mini App

Urolog-androlog **To'rayev Asror Abbosovich** uchun Telegram bot va uning ichidagi
Mini App (saytning Telegram versiyasi).

Bot: [@urolog_astorturayevbot](https://t.me/urolog_astorturayevbot) ·
Sayt: [urologasrorturayev.uz](https://urologasrorturayev.uz)

**Jonli manzillar**

| | |
|---|---|
| Servis | <https://urolog-asror-bot.onrender.com> |
| Mini App | <https://urolog-asror-bot.onrender.com/app/> |
| Repo | <https://github.com/shavkatovjurnalist-del/urolog-asror-bot> |
| Baza | Neon — `urolog` project (Frankfurt) |
| Hisobot boti | [@ai_humoyunbot](https://t.me/ai_humoyunbot) — arizalar va kunlik xulosa |

## Nima qiladi

| Bo'lim | Botda | Mini App'da |
|---|---|---|
| Shifokor haqida | ✅ rasm + tavsif | ✅ hero + bio |
| Xizmatlar (11 ta) | ✅ ro'yxat → batafsil | ✅ karta → pastki oyna |
| Jarrohlik usullari (6 ta) | ✅ | ✅ |
| Qabul joylari (2 klinika) | ✅ rasm + geolokatsiya | ✅ rasm + Yandex xarita |
| Natijalar (YouTube) | ✅ havolalar | ✅ preview karusel |
| Savol-javob | ✅ | ✅ akkordeon |
| Aloqa | ✅ | ✅ |
| **Qabulga yozilish** | ✅ bosqichma-bosqich | ✅ forma |
| **Murojaat (AI joyi)** | ✅ saqlanadi, AI kutilmoqda | ✅ |

Bot ham, Mini App ham **bitta bazadan** o'qiydi (`app/repo.py`), shuning uchun
ma'lumot har doim bir xil bo'ladi.

## Tuzilishi

```
app/
  config.py       .env sozlamalari
  models.py       baza jadvallari
  db.py           ulanish
  repo.py         o'qish/yozish (bot va API uchun umumiy)
  seed.py         sayt kontenti  ← matnni shu yerdan tahrirlang
  api.py          Mini App uchun JSON API
  webapp_auth.py  Telegram initData tekshiruvi
  ai.py           AI operator uchun bo'sh joy
  main.py         FastAPI: webhook + static + API
  bot/
    handlers.py   barcha bot mantiqi
    keyboards.py  tugmalar
    texts.py      matnlar
    instance.py   Bot/Dispatcher
webapp/           Mini App (index.html, style.css, app.js, assets/)
scripts/
  setup_bot.py    webhook, menyu tugmasi, komandalar
  smoke.py        tez tekshiruv
```

## Lokal ishga tushirish

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env        # BOT_TOKEN ni yozing
.venv\Scripts\python.exe -m app.seed
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8090
```

Mini App: <http://127.0.0.1:8090/app/> · API: `/api/content`

Faqat botni sinash uchun: `.venv\Scripts\python.exe run_polling.py`
(Mini App tugmalari faqat `BASE_URL` https bo'lganda chiqadi).

## Tekin serverga joylash (Render + Neon)

**1. Baza — [neon.tech](https://neon.tech) (tekin)**
Project yarating → `Connection string` ni nusxalang
(`postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require`).

**2. Kod — GitHub**

```bash
git init && git add . && git commit -m "urolog bot"
git remote add origin https://github.com/<user>/urolog-bot.git
git push -u origin main
```

**3. Server — [render.com](https://render.com) (Free plan)**
`New → Web Service` → GitHub repo → Render `render.yaml` ni o'zi topadi.
Environment bo'limiga yozing:

| Kalit | Qiymat |
|---|---|
| `BOT_TOKEN` | BotFather bergan token |
| `DATABASE_URL` | Neon connection string |
| `BASE_URL` | `https://<servis-nomi>.onrender.com` |
| `ADMIN_IDS` | shifokor/admin Telegram ID (botga `/id` yozib olinadi) |

**4. Deploy tugagach** — ilova o'zi webhook va Mini App menyu tugmasini o'rnatadi.
Qo'lda: `python -m scripts.setup_bot`

> ⚠️ Render Free plan 15 daqiqa harakatsizlikdan keyin uxlaydi (birinchi so'rov
> ~50 soniya sekin). [cron-job.org](https://cron-job.org) da har 10 daqiqada
> `https://<servis>.onrender.com/health` ni chaqirsangiz — doim uyg'oq turadi.

## Kodni yangilash

Servis Render API orqali yaratilgani uchun GitHub bilan avtomatik bog'lanish yo'q —
push qilingandan keyin deploy'ni qo'lda ishga tushirish kerak:

```bash
git push
curl -s -X POST -H "Authorization: Bearer <RENDER_API_KEY>" \
  -H "Content-Type: application/json" \
  https://api.render.com/v1/services/srv-d9so6rn40ujc73djrk60/deploys \
  -d '{"clearCache":"do_not_clear"}'
```

Avtomatik deploy kerak bo'lsa: Render dashboard → servis → `Settings` → `Build & Deploy`
→ GitHub akkauntini bir marta ulash. Shundan keyin har push o'zi deploy bo'ladi.

## Kontentni yangilash

Matn, xizmat, klinika yoki video qo'shish → `app/seed.py` ni tahrirlang va:

```bash
python -m app.seed
```

Bot ham, Mini App ham darhol yangi ma'lumotni ko'rsatadi.

## AI operatorni ulash

1. `.env` da `AI_ENABLED=true` va `AI_API_KEY=...`;
2. `app/ai.py` dagi `answer()` ichiga model chaqiruvini yozing.

Javob avtomatik ravishda `consultations.ai_answer` ga yoziladi va foydalanuvchiga
bot hamda Mini App orqali qaytariladi — boshqa kodni o'zgartirish shart emas.

## Adminlar uchun

| Buyruq | Vazifa |
|---|---|
| `/start` | menyu |
| `/id` | Telegram ID |
| `/stats` | foydalanuvchi, ariza va murojaat soni |

Har bir yangi ariza adminlarga «✅ Tasdiqlash / ❌ Bekor» tugmalari bilan keladi.
Tasdiqlansa — bemorga avtomatik xabar boradi.
