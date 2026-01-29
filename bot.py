import re
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from logger import get_logger
from config import API_ID, API_HASH, BOT_TOKEN, Y_GROUP_ID
from userbot import process_softurl
from shared_store import PENDING

log = get_logger("MAIN_BOT")

SOFTURL_REGEX = re.compile(r"https?://softurl\.in/\S+", re.IGNORECASE)

app = Client(
    "main_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@app.on_message(filters.private)
async def handler(_, message):
    try:
        text = message.text or message.caption
        if not text:
            return

        match = SOFTURL_REGEX.search(text)
        if not match:
            await message.reply("❌ softurl.in link nahi mila.")
            return

        softurl = match.group()

        # 🔹 COPY message to Y chat
        copied = await app.copy_message(
            chat_id=Y_GROUP_ID,
            from_chat_id=message.chat.id,
            message_id=message.id
        )

        # 🔹 store Y chat msg id
        PENDING[softurl] = (Y_GROUP_ID, copied.id)

        await message.reply("✅ Message sent & processing started")

        # 🔹 send softurl to X bot
        asyncio.create_task(process_softurl(softurl))

        log.info(f"Stored mapping: {softurl} -> {copied.id}")

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception:
        log.exception("bot handler error")

app.run()