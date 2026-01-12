import re
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from logger import get_logger
from config import API_ID, API_HASH, BOT_TOKEN
from userbot import process_link, check_status

log = get_logger("MAIN_BOT")

# simple URL detector
URL_REGEX = re.compile(r"https?://", re.IGNORECASE)

app = Client(
    "main_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@app.on_message(filters.private & filters.text)
async def main_handler(_, message):
    try:
        text = message.text.strip()

        # ---------- /check ----------
        if text == "/check":
            await message.reply("🔍 Status check ho raha hai, please wait...")
            asyncio.create_task(check_status(message.from_user.id))
            return

        # ---------- ignore all other commands ----------
        if text.startswith("/"):
            return

        # ---------- only accept messages with link ----------
        if not URL_REGEX.search(text):
            await message.reply("❌ Sirf valid link bhejo.")
            return

        # ---------- process user link ----------
        await message.reply("⏳ Link received, processing start...")
        asyncio.create_task(process_link(text))

    except FloodWait as e:
        log.warning(f"FloodWait main_handler {e.value}s")
        await asyncio.sleep(e.value)

    except Exception:
        log.exception("Unhandled error in bot")
        await message.reply("❌ Internal error, thodi der baad try karo.")

# ---------- START BOT ----------
try:
    log.info("Main bot started")
    app.run()
except Exception as e:
    log.critical(f"Bot crashed: {e}")