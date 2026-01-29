import re
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from logger import get_logger
from config import (
    API_ID, API_HASH, SESSION_STRING,
    X_BOT_USERNAME
)
from shared_store import PENDING

log = get_logger("USERBOT")

userbot = Client(
    "userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

URL_REGEX = re.compile(r"https?://\S+")
SOFTURL_REGEX = re.compile(r"https?://softurl\.in/\S+", re.IGNORECASE)

# -------- send softurl to X bot --------
async def process_softurl(link):
    try:
        await userbot.send_message(X_BOT_USERNAME, link)
        log.info(f"Softurl sent to X bot: {link}")
    except Exception:
        log.exception("process_softurl failed")

# -------- X BOT REPLY --------
@userbot.on_message(filters.chat(X_BOT_USERNAME))
async def xbot_reply(_, message):
    try:
        if not message.text:
            return

        softurl_match = SOFTURL_REGEX.search(message.text)
        if not softurl_match:
            return

        softurl = softurl_match.group()

        if softurl not in PENDING:
            return

        links = URL_REGEX.findall(message.text)
        if len(links) < 2:
            return

        new_link = [l for l in links if l != softurl][0]

        chat_id, msg_id = PENDING.pop(softurl)

        # 🔹 get current message text
        target = await userbot.get_messages(chat_id, msg_id)
        current_text = target.text or target.caption

        updated_text = current_text.replace(softurl, new_link)

        # 🔹 edit SAME message in Y chat
        await userbot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=updated_text
        )

        log.info("Y chat message edited successfully")

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception:
        log.exception("xbot_reply error")

# -------- START USERBOT --------
try:
    log.info("Userbot started")
    userbot.start()
except Exception as e:
    log.critical(f"Userbot crashed: {e}")