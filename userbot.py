import re
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from logger import get_logger
from config import API_ID, API_HASH, SESSION_STRING, X_BOT_USERNAME
from shared_store import TASKS

log = get_logger("USERBOT")

userbot = Client(
    "userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

URL_REGEX = re.compile(r"https?://\S+")
SOFTURL_REGEX = re.compile(r"https?://softurl\.in/\S+", re.IGNORECASE)

# ---------- send to X bot ----------
async def process_softurl(link):
    try:
        await userbot.send_message(X_BOT_USERNAME, link)
        log.info(f"Sent to X bot: {link}")
    except Exception as e:
        TASKS[link]["state"] = "error"
        TASKS[link]["error"] = str(e)

# ---------- X BOT REPLY ----------
@userbot.on_message(filters.chat(X_BOT_USERNAME))
async def xbot_reply(_, message):
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

        new_link = [l for l in links if l != softurl][0]

        task = TASKS[softurl]

        target = await userbot.get_messages(task["y_chat"], task["y_msg"])
        current_text = target.text or target.caption
        updated_text = current_text.replace(softurl, new_link)

        await userbot.edit_message_text(
            chat_id=task["y_chat"],
            message_id=task["y_msg"],
            text=updated_text
        )

        task["state"] = "done"

        log.info("Task completed")

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        log.exception("xbot_reply error")
        if softurl in TASKS:
            TASKS[softurl]["state"] = "error"
            TASKS[softurl]["error"] = str(e)

# ---------- START ----------
userbot.start()