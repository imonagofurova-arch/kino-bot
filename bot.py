import asyncio
import logging
import sqlite3
import os
 
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest
 
# ====== SOZLAMALAR ======
BOT_TOKEN = os.getenv("BOT_TOKEN", "BOT_TOKEN_NI_BU_YERGA_YOZING")
ADMIN_IDS = [5485806415]  # <-- o'zingizning Telegram ID raqamingizni shu yerga yozing
DB_PATH = "kino.db"
 
# Majburiy obuna kanallari.
# username bo'lsa "@" bilan yozing (masalan "@mychannel"), yopiq kanal bo'lsa -100... ko'rinishidagi ID yozing.
# Har bir element: (kanal_id_yoki_username, kanalga_havola, kanal_nomi)
FORCE_SUB_CHANNELS = [
    (-1003986899025, "https://t.me/+as1HUuKOrv1mYzJi", "1-kanal"),
    (-1004405457232, "https://t.me/urwelcomexxexe", "2-kanal"),
]
 
# Yangi kino qo'shilganda e'lon qilinadigan kanal.
# Bot shu kanalda ADMIN bo'lishi SHART (xabar yuborish huquqi bilan).
# Yopiq kanal bo'lsa -100... ko'rinishidagi ID yozing, ochiq bo'lsa "@kanal_username" yozing.
ANNOUNCE_CHANNEL_ID = -1004405457232
 
# Botning username'i (@ belgisisiz), deep-link tugmasi uchun kerak.
# Masalan bot manzili https://t.me/mybot bo'lsa, shu yerga "mybot" deb yozing.
BOT_USERNAME = "tungikinosex_bot"
 
logging.basicConfig(level=logging.INFO)
 
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
 
 
# ====== DATABASE ======
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            code TEXT PRIMARY KEY,
            file_id TEXT NOT NULL,
            title TEXT,
            added_by INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
 
 
def save_user(user_id: int, username: str, first_name: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
        (user_id, username, first_name),
    )
    conn.commit()
    conn.close()
 
 
def count_users() -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    n = cur.fetchone()[0]
    conn.close()
    return n
 
 
def save_movie(code: str, file_id: str, title: str, added_by: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO movies (code, file_id, title, added_by) VALUES (?, ?, ?, ?)",
        (code, file_id, title, added_by),
    )
    conn.commit()
    conn.close()
 
 
def get_movie(code: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT file_id, title FROM movies WHERE code = ?", (code,))
    row = cur.fetchone()
    conn.close()
    return row
 
 
def delete_movie(code: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM movies WHERE code = ?", (code,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted
 
 
def count_movies() -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM movies")
    n = cur.fetchone()[0]
    conn.close()
    return n
 
 
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS
 
 
# ====== MAJBURIY OBUNA ======
 
async def get_not_subscribed_channels(user_id: int):
    """Foydalanuvchi obuna bo'lmagan kanallar ro'yxatini qaytaradi."""
    not_subscribed = []
    for chat_id, link, name in FORCE_SUB_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status in (
                ChatMemberStatus.LEFT,
                ChatMemberStatus.KICKED,
            ):
                not_subscribed.append((chat_id, link, name))
        except TelegramBadRequest:
            # Bot kanalda admin emas yoki kanal ID noto'g'ri bo'lsa,
            # xatolikni log qilib, foydalanuvchini bloklamaymiz
            logging.warning(f"Force-sub tekshiruvida xatolik: {chat_id}")
    return not_subscribed
 
 
def build_subscribe_keyboard(channels):
    buttons = [
        [InlineKeyboardButton(text=f"📢 {name}", url=link)]
        for _, link, name in channels
    ]
    buttons.append(
        [InlineKeyboardButton(text="✅ Obuna bo'ldim", callback_data="check_sub")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)
 
 
async def send_subscribe_prompt(message: Message, channels):
    await message.answer(
        "⚠️ Botdan foydalanish uchun quyidagi kanal(lar)ga obuna bo'ling, "
        "so'ng <b>«✅ Obuna bo'ldim»</b> tugmasini bosing:",
        reply_markup=build_subscribe_keyboard(channels),
    )
 
 
@dp.callback_query(F.data == "check_sub")
async def callback_check_sub(callback: CallbackQuery):
    not_subscribed = await get_not_subscribed_channels(callback.from_user.id)
    if not_subscribed:
        await callback.answer("❌ Hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)
    else:
        await callback.message.edit_text("✅ Rahmat! Endi botdan foydalanishingiz mumkin.\n\nKino kodini yuboring.")
        await callback.answer()
 
 
# ====== KANALGA E'LON QILISH ======
 
async def announce_new_movie(code: str, title: str):
    """Yangi qo'shilgan kinoni e'lon kanaliga xabar qiladi, bosilsa botga o'tadigan tugma bilan."""
    if not ANNOUNCE_CHANNEL_ID:
        return
    display_title = title if title else f"Kod: {code}"
    deep_link = f"https://t.me/{BOT_USERNAME}?start={code}"
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🎬 Kinoni olish", url=deep_link)]]
    )
    try:
        await bot.send_message(
            chat_id=ANNOUNCE_CHANNEL_ID,
            text=f"🎬 <b>Yangi kino qo'shildi!</b>\n\n{display_title}\nKod: <code>{code}</code>",
            reply_markup=keyboard,
        )
    except TelegramBadRequest as e:
        logging.warning(f"Kanalga e'lon qilishda xatolik: {e}")
 
 
# ====== HANDLERLAR ======
 
async def send_movie_to_user(message: Message, code: str):
    result = get_movie(code)
    if result:
        file_id, title = result
        caption = f"🎬 {title}" if title else f"🎬 Kod: {code}"
        try:
            await message.answer_video(file_id, caption=caption)
        except Exception:
            await message.answer_document(file_id, caption=caption)
    else:
        await message.answer(
            f"❌ <b>{code}</b> kodli kino topilmadi.\nKodni tekshirib qaytadan yuboring."
        )
 
 
@dp.message(CommandStart())
async def cmd_start(message: Message):
    save_user(
        message.from_user.id,
        message.from_user.username or "",
        message.from_user.first_name or "",
    )
 
    if not is_admin(message.from_user.id):
        not_subscribed = await get_not_subscribed_channels(message.from_user.id)
        if not_subscribed:
            await send_subscribe_prompt(message, not_subscribed)
            return
 
    # Kanaldagi "🎬 Kinoni olish" tugmasidan kelgan bo'lsa (deep-link),
    # /start buyrug'i bilan birga kino kodi ham keladi: /start 1001
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1 and parts[1].strip().isdigit():
        await send_movie_to_user(message, parts[1].strip())
        return
 
    await message.answer(
        "🎬 Assalomu alaykum!\n\n"
        "Kino kodini yuboring, men sizga kinoni topib beraman.\n"
        "Masalan: <code>1001</code>\n\n"
        "Kod bilmasangiz, kanalimizdagi postlardan kodni ko'rishingiz mumkin."
    )
 
 
@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    total = count_movies()
    await message.answer(f"📊 Bazada jami <b>{total}</b> ta kino bor.")
 
 
def build_admin_panel():
    buttons = [
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🎬 Kino qo'shish yo'riqnomasi", callback_data="admin_addmovie_help")],
        [InlineKeyboardButton(text="🗑 Kino o'chirish yo'riqnomasi", callback_data="admin_delmovie_help")],
        [InlineKeyboardButton(text="📢 Majburiy kanallar ro'yxati", callback_data="admin_channels")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
 
 
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "🛠 <b>Admin panel</b>\n\nKerakli bo'limni tanlang:",
        reply_markup=build_admin_panel(),
    )
 
 
@dp.callback_query(F.data == "admin_stats")
async def callback_admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    total_movies = count_movies()
    total_users = count_users()
    await callback.message.edit_text(
        f"📊 <b>Statistika</b>\n\n"
        f"🎬 Jami kinolar: <b>{total_movies}</b>\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users}</b>",
        reply_markup=build_back_keyboard(),
    )
    await callback.answer()
 
 
@dp.callback_query(F.data == "admin_addmovie_help")
async def callback_admin_addmovie_help(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "🎬 <b>Kino qo'shish</b>\n\n"
        "1. Menga video (kino) yuboring\n"
        "2. Men kod so'rayman\n"
        "3. Siz shunchaki raqam yozasiz, masalan: <code>1001</code>\n\n"
        "Hammasi shu — boshqa hech narsa yozish shart emas!",
        reply_markup=build_back_keyboard(),
    )
    await callback.answer()
 
 
@dp.callback_query(F.data == "admin_delmovie_help")
async def callback_admin_delmovie_help(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "🗑 <b>Kino o'chirish</b>\n\n"
        "Buyruq: <code>/delete 1001</code>\n"
        "(1001 o'rniga o'chirmoqchi bo'lgan kodni yozing)",
        reply_markup=build_back_keyboard(),
    )
    await callback.answer()
 
 
@dp.callback_query(F.data == "admin_channels")
async def callback_admin_channels(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    if FORCE_SUB_CHANNELS:
        lines = "\n".join(f"• {name} — <code>{cid}</code>" for cid, _, name in FORCE_SUB_CHANNELS)
    else:
        lines = "Hech qanday majburiy kanal sozlanmagan."
    await callback.message.edit_text(
        f"📢 <b>Majburiy obuna kanallari</b>\n\n{lines}\n\n"
        "Kanal qo'shish/o'chirish uchun kod ichidagi FORCE_SUB_CHANNELS ro'yxatini tahrirlang.",
        reply_markup=build_back_keyboard(),
    )
    await callback.answer()
 
 
def build_back_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_back")]]
    )
 
 
@dp.callback_query(F.data == "admin_back")
async def callback_admin_back(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "🛠 <b>Admin panel</b>\n\nKerakli bo'limni tanlang:",
        reply_markup=build_admin_panel(),
    )
    await callback.answer()
 
 
@dp.message(Command("delete"))
async def cmd_delete(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Foydalanish: /delete <kod>")
        return
    code = parts[1].strip()
    if delete_movie(code):
        await message.answer(f"✅ <b>{code}</b> kodli kino o'chirildi.")
    else:
        await message.answer(f"❌ <b>{code}</b> kodli kino topilmadi.")
 
 
# Admin video/fayl yuborsa -> kod so'raladi va saqlanadi
# Caption ichida "kod: 1001" yoki shunchaki "1001" yozilsa, avtomatik o'sha kod bilan saqlanadi
@dp.message(F.video | F.document, F.from_user.func(lambda u: is_admin(u.id)))
async def admin_add_movie(message: Message):
    file_id = message.video.file_id if message.video else message.document.file_id
    caption = (message.caption or "").strip()
 
    # Captiondan kodni ajratib olishga harakat qilamiz (masalan "1001" yoki "kod:1001")
    code = None
    if caption:
        last_word = caption.split()[-1].replace("kod:", "").replace("Kod:", "").strip()
        if last_word.isdigit():
            code = last_word
 
    if code:
        save_movie(code, file_id, caption, message.from_user.id)
        await message.reply(
            f"✅ Kino saqlandi!\nKod: <code>{code}</code>"
        )
        await announce_new_movie(code, caption)
    else:
        # Kod topilmasa, adminga kod so'raymiz
        await message.reply(
            "🎬 Kino qabul qilindi!\n\nEndi shu kino uchun kodni yozing (masalan: <code>1001</code>)"
        )
        pending_movies[message.from_user.id] = (file_id, caption)
 
 
pending_movies = {}
 
 
@dp.message(Command("setcode"))
async def cmd_setcode(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or message.from_user.id not in pending_movies:
        await message.answer("Avval kino yuboring, keyin: /setcode <kod>")
        return
    code = parts[1].strip()
    file_id, caption = pending_movies.pop(message.from_user.id)
    save_movie(code, file_id, caption, message.from_user.id)
    await message.answer(f"✅ Kino saqlandi!\nKod: <code>{code}</code>")
    await announce_new_movie(code, caption)
 
 
# Oddiy foydalanuvchi kod yuborsa -> kino qidiriladi
# Admin bo'lsa va kutilayotgan kino bo'lsa -> shu raqam kod sifatida saqlanadi
@dp.message(F.text)
async def handle_code(message: Message):
    code = message.text.strip()
    if not code.isdigit():
        return  # kod raqam bo'lishi shart, boshqa matnlarga javob bermaymiz
 
    # Admin avval video yuborgan va endi kod kutilayotgan bo'lsa -> shu yerda saqlaymiz
    if is_admin(message.from_user.id) and message.from_user.id in pending_movies:
        file_id, caption = pending_movies.pop(message.from_user.id)
        save_movie(code, file_id, caption, message.from_user.id)
        await message.answer(f"✅ Kino saqlandi!\nKod: <code>{code}</code>")
        await announce_new_movie(code, caption)
        return
 
    if not is_admin(message.from_user.id):
        save_user(
            message.from_user.id,
            message.from_user.username or "",
            message.from_user.first_name or "",
        )
        not_subscribed = await get_not_subscribed_channels(message.from_user.id)
        if not_subscribed:
            await send_subscribe_prompt(message, not_subscribed)
            return
 
    await send_movie_to_user(message, code)
 
 
async def main():
    init_db()
    await dp.start_polling(bot)
 
 
if __name__ == "__main__":
    asyncio.run(main())
