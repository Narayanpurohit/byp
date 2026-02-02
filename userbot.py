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
from shortner import shorten_link

log = get_logger("USERBOT")

# ---------- REGEX ----------
URL_REGEX = re.compile(r"https?://\S+", re.IGNORECASE)
SOFTURL_REGEX = re.compile(r"https?://softurl\.in/\S+", re.IGNORECASE)

# ---------- CLIENT ----------
userbot = Client(
    "userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# ---------- SEND SOFTURL TO X BOT ----------
async def process_softurl(softurl: str):
    try:
        await userbot.send_message(X_BOT_USERNAME, softurl)
        log.info(f"Sent to X bot: {softurl}")

    except FloodWait as e:
        await asyncio.sleep(e.value)
        await process_softurl(softurl)

    except Exception as e:
        log.exception("process_softurl failed")
        task = TASKS.get(softurl)
        if task:
            batch_id = task.get("batch_id")
            if batch_id:
                batch = BATCHES.get(batch_id)
                if batch:
                    batch["errors"] += 1
                    batch["pending"].discard(softurl)
            TASKS.pop(softurl, None)

# ---------- HANDLE X BOT REPLY ----------
@userbot.on_message(filters.chat(X_BOT_USERNAME))
async def xbot_reply(_, message):
    softurl = None
    try:
        if not message.text:
            return

        # detect softurl
        soft_match = SOFTURL_REGEX.search(message.text)
        if not soft_match:
            return

        softurl = soft_match.group()
        task = TASKS.get(softurl)
        if not task:
            return

        # extract links
        links = URL_REGEX.findall(message.text)
        if len(links) < 2:
            raise ValueError("Second link not found")

        A_link = next(l for l in links if l != softurl)
        final_link = A_link

        # ---------- OPTIONAL SHORTENER ----------
        if SHORT_URL:
            try:
                final_link = await shorten_link(A_link)
            except Exception as e:
                log.warning(f"Shortener failed, using original link: {e}")
                final_link = A_link

        # ---------- FETCH Y MESSAGE ----------
        msg = await userbot.get_messages(task["y_chat"], task["y_msg"])
        text = msg.text or msg.caption
        if not text:
            raise ValueError("Target message has no editable text")

        # ---------- REPLACE LOGIC ----------
        text = text.replace(softurl, final_link)
        text = text.replace(REPLACE_FROM, REPLACE_TO)

        # ---------- EDIT ----------
        if msg.text:
            await userbot.edit_message_text(
                task["y_chat"], task["y_msg"], text
            )
        else:
            await userbot.edit_message_caption(
                task["y_chat"], task["y_msg"], text
            )

        # ---------- UPDATE BATCH ----------
        batch_id = task.get("batch_id")
        if batch_id:
            batch = BATCHES.get(batch_id)
            if batch:
                batch["edited"] += 1
                batch["pending"].discard(softurl)

        TASKS.pop(softurl, None)
        log.info(f"Task completed: {softurl}")

    except FloodWait as e:
        await asyncio.sleep(e.value)

    except Exception as e:
        log.exception("xbot_reply error")

        task = TASKS.get(softurl)
        if task:
            batch_id = task.get("batch_id")
            if batch_id:
                batch = BATCHES.get(batch_id)
                if batch:
                    batch["errors"] += 1
                    batch["pending"].discard(softurl)
            TASKS.pop(softurl, None)

# ---------- START USERBOT ----------
try:
    log.info("Userbot started")
    userbot.start()
except Exception as e:
    log.critical(f"Userbot crashed: {e}")