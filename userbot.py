import re
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, MessageNotModified
from logger import get_logger
from config import (
    API_ID,
    API_HASH,
    SESSION_STRING,
    X_BOT_USERNAME,
    B_BOT_USERNAME,
    SHORT_URL
)
from shared_store import TASKS, BATCHES
from shortner import shorten_link

log = get_logger("USERBOT")

SOFTURL_REGEX = re.compile(r"https?://softurl\.in/\S+", re.I)
URL_REGEX = re.compile(r"https?://\S+")

userbot = Client(
    "userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# ======================================================
# ADD TASK (🔥 THIS WAS MISSING)
# ======================================================
async def add_task(softurl, y_msg_id):
    """
    Entry point called by main bot
    """
    try:
        task = TASKS.get(softurl)
        if not task:
            return

        # batch counter
        batch_id = task.get("batch_id")
        if batch_id and batch_id in BATCHES:
            BATCHES[batch_id]["a_done"] += 1

        # send softurl to X bot
        await userbot.send_message(X_BOT_USERNAME, softurl)

        task["state"] = "sent_to_x"
        log.info(f"Task started for {softurl}")

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception:
        log.exception("add_task failed")
        if batch_id and batch_id in BATCHES:
            BATCHES[batch_id]["errors"] += 1


# ======================================================
# X BOT REPLY
# ======================================================
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
            return

        A_link = [l for l in links if l != softurl][0]

        TASKS[softurl]["A_link"] = A_link
        TASKS[softurl]["state"] = "got_A"

        await send_A_to_B(A_link, softurl)

    except Exception:
        log.exception("xbot_reply error")


# ======================================================
# SEND A LINK TO B BOT (reply based)
# ======================================================
async def send_A_to_B(A_link, softurl):
    try:
        link_msg = await userbot.send_message(
            B_BOT_USERNAME,
            A_link
        )

        await link_msg.reply("/genlink")

        TASKS[softurl]["state"] = "sent_to_b"
        log.info("A link sent and /genlink replied properly")

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception:
        log.exception("send_A_to_B failed")


# ======================================================
# B BOT REPLY
# ======================================================
@userbot.on_message(filters.chat(B_BOT_USERNAME))
async def bbot_reply(_, message):
    try:
        if not message.text:
            return

        match = URL_REGEX.search(message.text)
        if not match:
            return

        new_link = match.group()

        for softurl, task in list(TASKS.items()):
            if task.get("state") != "sent_to_b":
                continue

            final_link = new_link
            if SHORT_URL:
                try:
                    final_link = await shorten_link(new_link)
                except Exception:
                    pass

            await edit_y_message(softurl, final_link)
            TASKS.pop(softurl, None)

            batch_id = task.get("batch_id")
            if batch_id and batch_id in BATCHES:
                BATCHES[batch_id]["queue_done"] += 1

            break

    except Exception:
        log.exception("bbot_reply error")


# ======================================================
# EDIT Y MESSAGE
# ======================================================
async def edit_y_message(softurl, final_link):
    task = TASKS[softurl]

    msg = await userbot.get_messages(
        task["y_chat"],
        task["y_msg_id"]
    )

    text = msg.text or msg.caption
    new_text = text.replace(softurl, final_link)

    try:
        if msg.text:
            await userbot.edit_message_text(
                task["y_chat"],
                task["y_msg_id"],
                new_text
            )
        else:
            await userbot.edit_message_caption(
                task["y_chat"],
                task["y_msg_id"],
                new_text
            )
    except MessageNotModified:
        pass

    await userbot.edit_message_text(
        task["status_chat"],
        task["status_msg"],
        "✅ Processing completed"
    )


userbot.start()