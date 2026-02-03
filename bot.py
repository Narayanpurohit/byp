import re
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from logger import get_logger
from config import API_ID, API_HASH, BOT_TOKEN, Y_GROUP_ID
from shared_store import TASKS
from userbot import process_softurl

log = get_logger("BOT")

SOFTURL_REGEX = re.compile(r"https?://softurl\.in/\S+", re.I)

app = Client(
    "main_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@app.on_message(filters.private & filters.text)
async def handle_message(_, message):
    try:
        text = message.text
        match = SOFTURL_REGEX.search(text)
        if not match:
            return

        softurl = match.group()

        copied = await app.copy_message(
            Y_GROUP_ID,
            message.chat.id,
            message.id
        )

        status = await message.reply("⏳ Processing started...")

        TASKS[softurl] = {
            "y_chat": Y_GROUP_ID,
            "y_msg": copied.id,
            "status_chat": message.chat.id,
            "status_msg": status.id,
            "state": "sent_to_x"
        }

        asyncio.create_task(process_softurl(softurl))

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception:
        log.exception("handle_message error")

app.run()