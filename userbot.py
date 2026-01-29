import re
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from logger import get_logger
from config import (
    API_ID, API_HASH, SESSION_STRING,
    X_BOT_USERNAME, Y_GROUP_ID
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

        # extract softurl from reply
        softurl_match = SOFTURL_REGEX.search(message.text)
        if not softurl_match:
            return

        softurl = softurl_match.group()

        if softurl not in PENDING:
            return

        # extract all links (2 links expected)
        links = URL_REGEX.findall(message.text)
        if len(links) < 2:
            return

        new_link = [l for l in links if l != softurl][0]

        chat_id, msg_id = PENDING.pop(softurl)

        original = await userbot.get_messages(chat_id, msg_id)
        original_text = original.text or original.caption

        final_text = original_text.replace(softurl, new_link)

        # ----- send same type to Y group -----
        if original.text:
            await userbot.send_message(Y_GROUP_ID, final_text)

        elif original.photo:
            await userbot.send_photo(
                Y_GROUP_ID,
                original.photo.file_id,
                caption=final_text
            )

        elif original.document:
            await userbot.send_document(
                Y_GROUP_ID,
                original.document.file_id,
                caption=final_text
            )

        elif original.video:
            await userbot.send_video(
                Y_GROUP_ID,
                original.video.file_id,
                caption=final_text
            )

        elif original.audio:
            await userbot.send_audio(
                Y_GROUP_ID,
                original.audio.file_id,
                caption=final_text
            )

        log.info("Final message sent to Y group")

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