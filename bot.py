import asyncio
import logging
import sqlite3
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.enums import ParseMode

# ====== SOZLAMALAR ======
BOT_TOKEN = os.getenv("BOT_TOKEN", "BOT_TOKEN_NI_BU_YERGA_YOZING")
ADMIN_IDS = [123456789]  # <-- o'zingizning Telegram ID raqamingizni shu yerga yozing
DB_PATH = "kino.db"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
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
    conn.commit()
    conn.close()


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


# ====== HANDLERLAR ======

@dp.message(CommandStart())
async def cmd_start(message: Message):
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
    else:
        # Kod topilmasa, adminga kod so'raymiz
        await message.reply(
            "Kino qabul qilindi. Endi shu kino uchun kodni yuboring.\n"
            "Masalan: <code>/setcode 1001</code>"
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


# Oddiy foydalanuvchi kod yuborsa -> kino qidiriladi
@dp.message(F.text)
async def handle_code(message: Message):
    code = message.text.strip()
    if not code.isdigit():
        return  # kod raqam bo'lishi shart, boshqa matnlarga javob bermaymiz

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


async def main():
    init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
