import re
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from logger import get_logger
from config import (
    API_ID, API_HASH, SESSION_STRING,
    X_BOT_USERNAME, REPLACE_FROM, REPLACE_TO
)
from shared_store import TASKS, BATCHES

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
async def process_softurl(task_id, softurl):
    try:
        await userbot.send_message(X_BOT_USERNAME, softurl)
    except Exception:
        log.exception("process_softurl failed")
        TASKS.pop(task_id, None)

# ---------- X BOT REPLY ----------
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

        for tid, data in TASKS.items():
            if data["softurl"] == softurl:
                task_id = tid
                break

        if not task_id:
            return

        links = URL_REGEX.findall(message.text)
        if len(links) < 2:
            raise ValueError("Second link not found")

        A_link = [l for l in links if l != softurl][0]

        task = TASKS.get(task_id)
        if not task:
            return

        msg = await userbot.get_messages(task["y_chat"], task["y_msg"])
        text = msg.text or msg.caption

        text = text.replace(softurl, A_link)
        text = text.replace(REPLACE_FROM, REPLACE_TO)

        if msg.text:
            await userbot.edit_message_text(task["y_chat"], task["y_msg"], text)
        else:
            await userbot.edit_message_caption(task["y_chat"], task["y_msg"], text)

        # single message status update
        if task.get("status_chat"):
            await userbot.edit_message_text(
                task["status_chat"],
                task["status_msg"],
                "✅ Processing completed"
            )

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

userbot.start()