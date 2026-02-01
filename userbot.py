import re
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, RPCError
from logger import get_logger
from config import (
    API_ID,
    API_HASH,
    SESSION_STRING,
    X_BOT_USERNAME,
    SHORT_URL
)
from shared_store import TASKS
from shortner import shorten_link
from config import REPLACE_FROM, REPLACE_TO


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

# ---------- SEND LINK TO X BOT ----------
async def process_softurl(softurl: str):
    try:
        await userbot.send_message(X_BOT_USERNAME, softurl)
        log.info(f"Softurl sent to X bot: {softurl}")

    except FloodWait as e:
        log.warning(f"FloodWait process_softurl {e.value}s")
        await asyncio.sleep(e.value)
        await process_softurl(softurl)

    except RPCError as e:
        log.error(f"RPCError process_softurl: {e}")
        TASKS[softurl]["state"] = "error"
        TASKS[softurl]["error"] = str(e)

    except Exception as e:
        log.exception("process_softurl failed")
        TASKS[softurl]["state"] = "error"
        TASKS[softurl]["error"] = str(e)

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

        if softurl not in TASKS:
            log.warning(f"Unknown softurl ignored: {softurl}")
            return

        # extract all links
        links = URL_REGEX.findall(message.text)
        if len(links) < 2:
            raise ValueError("Second link not found in X bot reply")

        # second link = A link
        A_link = [l for l in links if l != softurl][0]
        final_link = A_link

        # ---------- SHORTENER ----------
        if SHORT_URL:
            try:
                final_link = await shorten_link(A_link)
                log.info("Link shortened successfully")
            except Exception as e:
                log.warning(f"Shortener failed, using original link: {e}")
                final_link = A_link

        task = TASKS[softurl]

        # fetch copied Y message
        target = await userbot.get_messages(
            task["y_chat"],
            task["y_msg"]
        )

        old_text = target.text or target.caption
        if not old_text:
            raise ValueError("Target message has no editable text")

        new_text = old_text.replace(softurl, final_link)

        # simple fixed replace
        new_text = new_text.replace(REPLACE_FROM, REPLACE_TO)
        # ---------- EDIT MESSAGE ----------
        if target.text:
            await userbot.edit_message_text(
                chat_id=task["y_chat"],
                message_id=task["y_msg"],
                text=new_text
            )
        else:
            await userbot.edit_message_caption(
                chat_id=task["y_chat"],
                message_id=task["y_msg"],
                caption=new_text
            )

        task["state"] = "done"
        log.info(f"Task completed for {softurl}")

    except FloodWait as e:
        await asyncio.sleep(e.value)

    except Exception as e:
        log.exception("xbot_reply error")
        if softurl and softurl in TASKS:
            TASKS[softurl]["state"] = "error"
            TASKS[softurl]["error"] = str(e)

# ---------- START USERBOT ----------
try:
    log.info("Userbot started")
    userbot.start()
except Exception as e:
    log.critical(f"Userbot crashed: {e}")