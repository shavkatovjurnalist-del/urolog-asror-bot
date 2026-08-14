"""AI-konsultant uchun bilim bazasi — shifokor anketasidan (134 savol).

Manba: `asror-torayev-anketa.txt`, To'rayev Asror Abbosovich, 2026-08-11.
Bu fayl **faktlarni** saqlaydi. Uslub va chegaralar — `app/persona.py` da.

Ikkinchi manba — bazadagi kontent (xizmatlar, usullar, FAQ, klinika, shifokor
profili). U `app/ai.py: build_context()` da shu matnga qo'shiladi. Ya'ni AI
ikkita bazadan oziqlanadi: umumiy kontent + anketaning aniqlashtiruvchi javoblari.

NARXLAR HAQIDA
Anketada «AI narxni aytmasin» degan javob bor edi, lekin Bobur 2026-08-11 da
buni xato deb tuzatdi: **AI barcha narxlarni ayta oladi**. Narxlar quyidagi
`PRICE_FACTS` bo'limida. Yagona qoida — bu narxlar boshlang'ich, aniq summa
holatga qarab ko'rikdan keyin belgilanadi; AI shuni eslatib qo'yadi.
"""
from __future__ import annotations

PHONE = "+998 90 008 38 78"

# ─────────────────────────────────────────────────────────────────────
#  1. Shifokor va qabul joyi
# ─────────────────────────────────────────────────────────────────────
DOCTOR_FACTS = """
SHIFOKOR
To'rayev Asror Abbosovich — urolog-androlog, oliy toifali.
Tajriba: 5 yildan beri amaliyotda, 4000 dan ortiq operatsiya bajargan,
yiliga o'rtacha 1000 ta operatsiya.
Ta'lim: 2020 — Toshkent tibbiyot akademiyasi (bakalavr);
2022 — Urologiya markazida ordinatura. Xorijiy malaka oshirish: penil protez.

Nega aynan u:
- eng zamonaviy usullar bilan ishlaydi;
- mikroskop ostida Marmar operatsiyasini Samarqandda birinchi bo'lib
  2024-yilda aynan o'zi boshlagan;
- Samarqandda penil protezni faqat o'zi o'rnatadi;
- denervatsiyani ham faqat o'zi qiladi.

QABUL JOYI — FAQAT BITTA
Sintez Lab klinikasi, Samarqand shahri, Laxuti ko'chasi 2A.
Mo'ljal: 6-hammom, Brilliant City, Ikar chorrahasi. 1-qavat.
Boshqa hech qaysi manzilda qabul yo'q.
Hozircha faqat Samarqandda qabul qiladi — boshqa shaharlarga bormaydi.

OPERATSIYA QAYERDA BAJARILADI
Operatsiya uchun barcha sharoit bor: statsionar, palata va reanimatsiya.
Bemor operatsiya manzilini so'rasa — Sintez Lab manzilini berish mumkin
(Samarqand, Laxuti ko'chasi 2A), lekin uni operatsiya joyi deb emas,
KO'RIK VA TEKSHIRUV joyi deb ayt: barcha ko'rik, tahlil va UZI shu yerda
bo'ladi; operatsiya masalasini Asror Abbosovichning o'zi qabulda
tushuntiradi. Boshqa bino nomini yoki manzilini HECH QACHON aytma.
Namuna: «Barcha ko'rik va tekshiruvlar Sintez Lab klinikasida — Laxuti
ko'chasi 2A da bo'ladi. Operatsiya uchun barcha sharoit bor: statsionar,
palata, reanimatsiya. Qolganini Asror Abbosovichning o'zi qabulda aytadi.»

ISH VAQTI
Qabul kunlari: dushanba – juma, haftasiga 5 kun, soat 09:00 dan 16:00 gacha.
Tushlik: 13:00 – 14:00. Shanba va yakshanba — dam olish.
Bayram kunlari ishlamaydi.
Operatsiya kunlari ham dushanba – juma; o'sha kunlari qabul ham bo'ladi.

ALOQA
Telefon (Telegram ham shu raqamda): {phone}
Instagram: @urolog_asrorturayev
Telegram kanal: @urolog_samarqand
YouTube: samarqand_urolog
Sayt: urologasrorturayev.uz
Elektron pochta ishlatilmaydi. Bemor email so'rasa, manzil berma —
telefon, Telegram yoki Instagram orqali bog'lanishni taklif qil.
""".strip().format(phone=PHONE)

# ─────────────────────────────────────────────────────────────────────
#  2. Qabulga yozilish tartibi
# ─────────────────────────────────────────────────────────────────────
BOOKING_FACTS = """
QABULGA YOZILISH
Navbat jonli — oldindan qat'iy yozilish shart emas. Bemor keladigan kuni
telefon qilib keladi. Oldindan yozilmasdan kelgan bemor ham qabul qilinadi.
Avans yoki oldindan to'lov yo'q. Kelolmay qolsa oldindan ogohlantirish shart emas.
O'zi bilan hech narsa olib kelishi shart emas.
Botda «Qabulga yozilish» tugmasi bor — ism, telefon va qulay vaqtni qoldirsa
bo'ladi, keyin shifokor jamoasi bog'lanadi.
Yozilayotganda kerakli ma'lumot: ism va telefon raqami.

BOSHQA SHAHAR VA CHET ELDAN KELUVCHILAR
Samarqandda 1-3 kun turish yetarli. Bir kunda ko'rik va operatsiya bo'lishi mumkin.
Mehmonxona bo'yicha yordam berilmaydi.
Analizlarni o'z shahrida topshirib kelish tavsiya etilmaydi — shu yerda topshiriladi.
Rossiya, Qozog'iston, Tojikiston, Afg'onistondan kelgan bemorlar qabul qilinadi.
""".strip()

# ─────────────────────────────────────────────────────────────────────
#  3. Analizlar va tekshiruvlar (narxsiz, faqat tayyorgarlik va muddat)
# ─────────────────────────────────────────────────────────────────────
LAB_FACTS = """
ANALIZ VA TEKSHIRUVLAR
Klinikada to'liq laboratoriya va ultratovush bor. Oldindan yozilish shart emas.
Natija qo'lda beriladi. Boshqa laboratoriyada topshirilgan analiz ham qabul
qilinadi — 3 oy davomida amal qiladi.

Spermogramma: 3 kun jinsiy aloqadan tiyilish kerak; alkogol, hammom, dori va
isitma bo'lmasligi shart. Klinikada topshiriladi, natija 2 soatda tayyor.
Kruger morfologiyasi, MAR-test va sperma DNK fragmentatsiyasi — yo'q.

PSA (umumiy va erkin): maxsus tayyorgarlik shart emas, natija 1 kunda.
40 yoshdan boshlab topshirish tavsiya etiladi.

Gormonlar (testosteron, FSH, LH, prolaktin, estradiol): och qoringa,
soat 09:00 gacha, tish yuvmasdan va suv ichmasdan topshiriladi.

Siydik umumiy tahlili: 1-porsiya siydik.
Qon tahlillari: och qoringa.

Jinsiy yo'l infeksiyalari (PCR / surtma): barcha infeksiyalar tekshiriladi,
siyilmagan holatda topshiriladi, natija 1 kundan 5 kungacha.

UZI turlari: buyrak va siydik pufagi UZI (siydik qistagan holatda kelinadi),
moyak (skrotal) UZI + doppler, TRUZI — prostatani transrektal ko'rish
(klizma qilib kelish kerak), jinsiy olat doppleri.

Klinikada YO'Q: uroflowmetriya, KT, MRT, rentgen (urografiya),
masofaviy litotripsiya (ESWL).

Bemor analiz javobini rasmga olib yuborsa — shifokor bepul ko'rib izohlaydi.
""".strip()

# ─────────────────────────────────────────────────────────────────────
#  4. Operatsiyalar (narxsiz)
# ─────────────────────────────────────────────────────────────────────
SURGERY_FACTS = """
BAJARILADIGAN OPERATSIYALAR
Erkaklar salomatligi: penil protez, varikotsele (mikroskopik Marmar),
gidrotsele, moyak ortig'i kistasi / spermatosele, TESE va Micro-TESE,
denervatsiya (tez bo'shanish), ligamentotomiya, sunnat (xatna),
frenulotomiya / frenuloplastika, jinsiy olat egriligini to'g'rilash (Peyroni),
fimoz va parafimoz, papilloma kuydirish.
Buyrak, prostata, pufak: HoLEP / MoLEP, TUR, prostatektomiya, PCNL, URS / RIRS,
buyrak operatsiyalari (rezeksiya, nefrektomiya, kista), siydik pufagi
operatsiyalari, uretra plastikasi, ayollarda TVT / TOT, bolalar operatsiyalari
(kriptorxizm, gidrosele, fimoz, gipospadiya), shoshilinch operatsiyalar.
Onkologiya bilan shug'ullanmaydi — bunday bemorlar boshqa mutaxassisga
yo'naltiriladi.

PENIL PROTEZ
Operatsiya 2-3 soat, spinal anesteziya, 1 kun kasalxonada yotiladi,
to'liq tiklanish 1 oy. 1 komponentli va 3 komponentli turlari bor.
Brendlar: Promedon va AMS 700.
Kafolat muddati — 5 yil. Protez necha yil xizmat qilishi haqida boshqa raqam
aytilmaydi: «umrbod», «cheksiz» yoki «20 yil» kabi gaplar noto'g'ri.
Faqat shu deyiladi: protezga 5 yil kafolat beriladi.
Jinsiy hayotga 1 oydan keyin qaytiladi. Tashqaridan bilinmaydi, tabiiy ko'rinadi.

VARIKOTSELE — MIKROSKOPIK MARMAR
1-2 soat, mahalliy anesteziya (superkain bilan muzlatib), kasalxonada
yotilmaydi. Mikroskop ostida muhim tuzilmalar — limfa, arteriya va ductus
deferens — ajratiladi, oddiy usuldan farqi shu. Tiklanish 1 oy, sportga va
og'ir yukka 1 oydan keyin. Spermogramma 3-6 oydan keyin yaxshilanadi.
Qayta chiqib ketish ehtimoli yo'q.

GIDROTSELE: 1 soat, mahalliy anesteziya, yotilmaydi, tiklanish 1 oy,
chandiq qoladi.

MOYAK ORTIG'I KISTASI / SPERMATOSELE: 1 soat, mahalliy anesteziya,
o'sha kuni uyga ketiladi, tiklanish 1 oy.

Bir kunlik (ambulator) operatsiyalar: varikotsele, moyak ortig'i kistasi,
gidrotsele (vodyanka), denervatsiya.

OPERATSIYAGA TAYYORGARLIK
Majburiy analizlar: OIV (SPID), gepatit B, gepatit C, sifilis.
Umumiy analizlar va flyuorografiya / EKG 1 oy amal qiladi.
Operatsiyadan 2 soat oldin ovqat yeyilmaydi, suv ichilmaydi.
Klizma shart emas. Tuklarni uyda tozalab kelish kerak.
Chekish, alkogol va dorilarni to'xtatish talab qilinmaydi.
O'zi bilan hech narsa olib kelishi shart emas. Hamroh kerak, palatada bepul
qoladi; ko'pchilik bemor operatsiyadan keyin uyga o'zi ketadi.
Surunkali kasalliklar (diabet, gipertoniya, yurak, semizlik) klinikada
alohida gaplashiladi.
Operatsiya kechiktiriladi: o'tkir infeksiya, yuqori qand, qon ivishi buzilganda.

OPERATSIYADAN KEYIN (UMUMIY MUDDATLAR)
Quyidagilar umumiy — agar yuqorida aniq operatsiya uchun boshqa muddat
ko'rsatilgan bo'lsa, O'SHA USTUN turadi. Masalan varikotseledan keyin sportga
1 oydan keyin qaytiladi, umumiy 20 kun emas.
O'rtacha 1-2 kun kasalxonada yotiladi.
Ishga va mashina haydashga 10 kundan keyin; sport, og'ir yuk, jinsiy hayot,
cho'milish, hammom, sauna va uzoq safar — 20 kundan keyin.
Alkogol va muzdek ichimlik mumkin emas.
Tikuv 10-12 kun orasida olinadi. Bog'lam uyda almashtiriladi, bog'lam uchun
klinikaga kelish shart emas.
Nazorat ko'riklari: 10 kundan keyin, so'ng 30 kun va 3 oydan keyin.
Operatsiya qilingan bemor uchun nazorat ko'rigi bir marta bepul.
Chidab bo'lmas kuchli og'riq paydo bo'lsa — zudlik bilan shifokorga.
Operatsiyadan keyin bemor shifokor bilan {phone} raqami orqali,
istalgan vaqtda bog'lanadi.
""".strip().format(phone=PHONE)

# ─────────────────────────────────────────────────────────────────────
#  5. To'lov, bemor toifalari, kafolat
# ─────────────────────────────────────────────────────────────────────
PATIENT_FACTS = """
TO'LOV
To'lov naqd qabul qilinadi. Bo'lib to'lash yo'q. Tibbiy sug'urta (DMS) va
davlat kvotasi bo'yicha ishlanmaydi. Chek beriladi.
Operatsiya bekor qilinsa to'langan pul qaytariladi.
Kutilmagan qo'shimcha xarajat bo'lishi mumkin bo'lgan yagona narsa — analizlar.
Chegirma yoki imtiyoz toifalari yo'q.

BEMOR TOIFALARI
1 yoshdan 65+ gacha, bolalar ham qabul qilinadi.
Ayollar qabul qilinadi — asosan siydik tutolmaslik muammosi bilan.
Urologik va andrologik bo'lmagan kasalliklar bilan bemorlar qabul qilinmaydi,
boshqa mutaxassisga yo'naltiriladi.

KAFOLAT
Meditsinada kafolat yo'q — ertaga nima bo'lishini faqat Xudo biladi.
Ammo asorat chiqsa, qayta davolash uchun pul olinmaydi.

MAXFIYLIK
Bemorning barcha shaxsiy ma'lumotlari faqat o'ziga aytiladi.

NATIJALAR
Bemorlarning natijalarini Telegram kanalidan (@urolog_samarqand) ko'rish
mumkin, yoki qabulga kelib shifokorning kompyuteridan ko'rsa bo'ladi.
""".strip()

# ─────────────────────────────────────────────────────────────────────
#  6. Narxlar
#     Anketadan. Bemor so'rasa AI aynan shu raqamlarni aytadi.
#     Bu yerda yo'q narxni O'YLAB TOPMAYDI — «aniq narxni shifokor aytadi» deydi.
# ─────────────────────────────────────────────────────────────────────
PRICE_FACTS = """
NARXLAR
Quyidagi narxlarni bemorga bemalol aytish mumkin. Aytishdan oldin yoki keyin
bir og'iz eslatib qo'y: aniq summa holatga qarab ko'rikdan keyin belgilanadi.
Ro'yxatda yo'q narxni o'ylab topma — «buni shifokorning o'zi aytadi» de.

Konsultatsiya:
- birlamchi konsultatsiya — 200 000 so'm, 10-15 daqiqa davom etadi.
  Bu narxga FAQAT SUHBAT kiradi. UZI va analizlar unga kirmaydi, alohida
  hisoblanadi. «Ko'rik ham narxga kiradi» deb aytma — bu noto'g'ri.
- takroriy konsultatsiya — 100 000 so'm (15 kun ichida)
- operatsiyadan keyingi nazorat ko'rigi — 1 marta bepul
- analiz javobini rasmdan ko'rib izohlash — bepul
- onlayn konsultatsiya — yo'q

Analizlar va tekshiruvlar:
- spermogramma — 105 000 so'mdan boshlanadi
- PSA umumiy — 300 000 so'm; PSA erkin — 300 000 so'm
  (bu aniq narx: «300 000 dan» yoki «taxminan» deb aytma)
- gormon tahlillari — har biri taxminan 110 000 so'm
- siydik umumiy tahlili — 55 000 so'm
- qon umumiy tahlili — taxminan 70 000 so'm
- qon biokimyosi — turiga qarab har xil
- jinsiy infeksiyalar paketi (PCR) — 800 000 so'm
- buyrak va siydik pufagi UZI — 100 000 so'm
- moyak (skrotal) UZI + doppler — 100 000 so'm
- TRUZI — 100 000 so'm
- jinsiy olat doppleri — 100 000 so'm

Erkaklar salomatligi operatsiyalari:
- penil protez — 29 mln so'mdan 168 mln so'mgacha
  (1 komponentli 29 mln, 3 komponentli 168 mln)
- varikotsele (Marmar) — bir tomon 3 mln, ikki tomon 5 mln so'm
- gidrotsele — 3,5 mln so'm
- moyak ortig'i kistasi / spermatosele — 2-3 mln so'm
- TESE / Micro-TESE — taxminan 15 mln so'm
- denervatsiya (tez bo'shanish) — 8 mln so'm
- ligamentotomiya (uzunlikni oshirish) — 11 mln so'm
- sunnat (xatna) — 1,5 mln so'm
- fimoz / parafimoz — 5 mln so'm
- Peyroni (egrilikni to'g'rilash) — 1000-4000 dollar atrofida
- papilloma kuydirish — 200 dollardan boshlanadi
- frenulotomiya / frenuloplastika — narxi kelishiladi

Buyrak, prostata, pufak operatsiyalari:
- HoLEP / MoLEP — 13-16 mln so'm
- TUR (prostata) — 9-10 mln so'm
- prostatektomiya — 30-80 mln so'm
- PCNL — 7-15 mln so'm
- URS / RIRS — 7-15 mln so'm
- buyrak operatsiyalari (rezeksiya, nefrektomiya, kista) — 10-30 mln so'm
- siydik pufagi operatsiyalari — 10-15 mln so'm
- uretra plastikasi — 20-30 mln so'm
- TVT / TOT (ayollarda siydik tutolmaslik) — 8-12 mln so'm
- bolalar operatsiyalari — 5 mln so'm
- shoshilinch operatsiyalar — 10-15 mln so'm
- ESWL (masofaviy litotripsiya) — bizda yo'q

Operatsiya narxiga operatsiyaning o'zi va unda ishlatiladigan buyumlar kiradi.
Qo'shimcha xarajat bo'lishi mumkin bo'lgan yagona narsa — analizlar.
Chegirma va imtiyoz toifalari yo'q.
""".strip()

# ─────────────────────────────────────────────────────────────────────
#  Yig'ilgan bilim bazasi
# ─────────────────────────────────────────────────────────────────────
KNOWLEDGE = "\n\n".join(
    [DOCTOR_FACTS, BOOKING_FACTS, LAB_FACTS, SURGERY_FACTS, PATIENT_FACTS, PRICE_FACTS]
)


def knowledge_text() -> str:
    """Anketadan olingan faktlar — AI kontekstiga qo'shiladi."""
    return KNOWLEDGE
