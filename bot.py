import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from logger import get_logger
from config import BOT_TOKEN, API_ID, API_HASH
from userbot import process_link, check_status

log = get_logger("MAIN_BOT")

app = Client(
    "main_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@app.on_message(filters.private & filters.text)
async def handler(_, message):
    try:
        text = message.text.strip()

        if text == "/check":
            await message.reply("🔍 Status check started...")
            asyncio.create_task(check_status(message.from_user.id))
            return

        await message.reply("⏳ Link received, processing...")
        asyncio.create_task(process_link(text))

    except FloodWait as e:
        log.warning(f"FloodWait: sleeping {e.value}s")
        await asyncio.sleep(e.value)

    except Exception as e:
        log.exception("Unhandled error in bot")
        await message.reply("❌ Internal error, try again later.")

try:
    log.info("Main bot started")
    app.run()
except Exception as e:
    log.critical(f"Bot crashed: {e}")