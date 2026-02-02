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
    REPLACE_FROM,
    REPLACE_TO,
    SHORT_URL
)
from shared_store import TASKS, BATCHES
from shortner import shorten_link

log = get_logger("USERBOT")

URL_REGEX = re.compile(r"https?://\S+")
SOFTURL_REGEX = re.compile(r"https?://softurl\.in/\S+", re.IGNORECASE)

userbot = Client(
    "userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# ---------- SEND SOFTURL TO X BOT ----------
async def process_softurl(task_id: str, softurl: str):
    try:
        await userbot.send_message(X_BOT_USERNAME, softurl)
    except Exception:
        log.exception("process_softurl failed")
        TASKS.pop(task_id, None)

# ---------- HANDLE X BOT REPLY ----------
@userbot.on_message(filters.chat(X_BOT_USERNAME))
async def xbot_reply(_, message):
    task_id = None
    try:
        if not message.text:
            return

        soft_match = SOFTURL_REGEX.search(message.text)
        if not soft_match:
            return

        softurl = soft_match.group()

        # find related task
        for tid, data in TASKS.items():
            if data.get("softurl") == softurl:
                task_id = tid
                break

        if not task_id:
            return

        links = URL_REGEX.findall(message.text)
        if len(links) < 2:
            raise ValueError("Second link not found")

        A_link = [l for l in links if l != softurl][0]
        final_link = A_link

        # ---------- SHORT URL ----------
        if SHORT_URL:
            try:
                final_link = await shorten_link(A_link)
            except Exception:
                log.warning("Shortener failed, using original link")
                final_link = A_link

        task = TASKS.get(task_id)
        if not task:
            return

        msg = await userbot.get_messages(task["y_chat"], task["y_msg"])
        text = msg.text or msg.caption or ""

        # ---------- REPLACE ----------
        text = text.replace(softurl, final_link)
        text = text.replace(REPLACE_FROM, REPLACE_TO)

        if msg.text:
            await userbot.edit_message_text(task["y_chat"], task["y_msg"], text)
        else:
            await userbot.edit_message_caption(task["y_chat"], task["y_msg"], text)

        # ---------- SINGLE STATUS UPDATE ----------
        if task.get("status_chat"):
            await userbot.edit_message_text(
                task["status_chat"],
                task["status_msg"],
                "✅ Processing completed"
            )

        # ---------- BATCH UPDATE ----------
        batch_id = task.get("batch_id")
        if batch_id:
            batch = BATCHES.get(batch_id)
            if batch:
                batch["edited"] += 1
                batch["pending"].discard(task_id)

        TASKS.pop(task_id, None)

    except FloodWait as e:
        await asyncio.sleep(e.value)

    except Exception:
        log.exception("xbot_reply error")
        if task_id:
            task = TASKS.pop(task_id, None)
            if task:
                batch_id = task.get("batch_id")
                batch = BATCHES.get(batch_id)
                if batch:
                    batch["errors"] += 1
                    batch["pending"].discard(task_id)

# ---------- START USERBOT ----------
try:
    log.info("Userbot started")
    userbot.start()
except Exception as e:
    log.critical(f"Userbot crashed: {e}")