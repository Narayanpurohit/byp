import re
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from logger import get_logger
from config import (
    API_ID,
    API_HASH,
    SESSION_STRING,
    X_BOT_USERNAME,
    SHORT_URL,
    REPLACE_FROM,
    REPLACE_TO
)
from shared_store import TASKS, BATCHES
from shortener import shorten_link

log = get_logger("USERBOT")

URL_REGEX = re.compile(r"https?://\S+")
SOFTURL_REGEX = re.compile(r"https?://softurl\.in/\S+", re.IGNORECASE)

userbot = Client(
    "userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# ---------- SEND TO X BOT ----------
async def process_softurl(softurl):
    await userbot.send_message(X_BOT_USERNAME, softurl)

# ---------- HANDLE X BOT REPLY ----------
@userbot.on_message(filters.chat(X_BOT_USERNAME))
async def xbot_reply(_, message):
    softurl = None
    try:
        if not message.text:
            return

        soft_match = SOFTURL_REGEX.search(message.text)
        if not soft_match:
            return

        softurl = soft_match.group()
        if softurl not in TASKS:
            return

        links = URL_REGEX.findall(message.text)
        if len(links) < 2:
            raise ValueError("Second link not found")

        A_link = [l for l in links if l != softurl][0]
        final_link = A_link

        if SHORT_URL:
            try:
                final_link = await shorten_link(A_link)
            except Exception:
                final_link = A_link

        task = TASKS[softurl]

        msg = await userbot.get_messages(task["y_chat"], task["y_msg"])
        text = msg.text or msg.caption

        text = text.replace(softurl, final_link)
        text = text.replace(REPLACE_FROM, REPLACE_TO)

        if msg.text:
            await userbot.edit_message_text(task["y_chat"], task["y_msg"], text)
        else:
            await userbot.edit_message_caption(task["y_chat"], task["y_msg"], text)

        batch_id = task.get("batch_id")
        if batch_id and batch_id in BATCHES:
            BATCHES[batch_id]["edited"] += 1
            BATCHES[batch_id]["pending"].discard(softurl)

        TASKS.pop(softurl, None)

    except FloodWait as e:
        await asyncio.sleep(e.value)

    except Exception as e:
        log.exception("xbot_reply error")
        if softurl in TASKS:
            batch_id = TASKS[softurl].get("batch_id")
            if batch_id and batch_id in BATCHES:
                BATCHES[batch_id]["errors"] += 1
                BATCHES[batch_id]["pending"].discard(softurl)
            TASKS.pop(softurl, None)

userbot.start()