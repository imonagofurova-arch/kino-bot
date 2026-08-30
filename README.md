# 🎬 Kino Kod Bot

Foydalanuvchi kod yuborsa, mos kino (video) qaytariladigan Telegram bot.

## O'rnatish

1. Python 3.10+ o'rnatilgan bo'lishi kerak.

2. Kerakli kutubxonani o'rnating:
```bash
pip install -r requirements.txt
```

3. [@BotFather](https://t.me/BotFather) orqali bot yarating va tokenni oling.

4. `bot.py` faylida:
   - `BOT_TOKEN` ga o'z tokeningizni yozing (yoki `BOT_TOKEN` environment variable qiling)
   - `ADMIN_IDS` ro'yxatiga o'zingizning Telegram ID raqamingizni yozing
     (ID ni bilish uchun [@userinfobot](https://t.me/userinfobot) ga yozing)

5. Botni ishga tushiring:
```bash
python bot.py
```

## Foydalanish

### Admin uchun — kino qo'shish
1. Botga video yoki fayl (kino) yuboring
2. Video captionida oxirgi so'z sifatida kodni yozsangiz (masalan: `Avengers 1001`),
   bot avtomatik shu kod bilan saqlaydi
3. Caption yozmasangiz, bot kodni so'raydi — `/setcode 1001` deb yuboring

### Admin buyruqlari
- `/stats` — bazadagi kinolar sonini ko'rsatadi
- `/delete 1001` — shu kod bilan saqlangan kinoni o'chiradi

### Foydalanuvchi uchun
- Botga shunchaki kino kodini (masalan `1001`) yuborsa, bot mos videoni qaytaradi

## Eslatma

- Ma'lumotlar `kino.db` (SQLite) faylida saqlanadi — kino fayllarning o'zi emas,
  balki Telegram file_id saqlanadi, shuning uchun bot juda tez va yengil ishlaydi.
- Bot 24/7 ishlashi uchun uni VPS yoki serverga joylashtirishingiz kerak
  (mahalliy kompyuterda ishga tushirsangiz, kompyuter o'chganda bot ham to'xtaydi).
- Ko'p kino bo'lsa, kinolarni avval o'zingizning yopiq (admin) kanalingizga
  yuklab, keyin botga forward qilishingiz mumkin — bu tartibni saqlashga yordam beradi.
