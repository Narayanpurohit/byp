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

TASK_QUEUE = []
CURRENT_TASK = None

userbot = Client(
    "userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# ======================================================
# ADD TASK (CALLED FROM BOT)
# ======================================================
async def add_task(softurl, y_msg_id):
    if softurl not in TASK_QUEUE:
        TASK_QUEUE.append(softurl)
        TASKS[softurl]["state"] = "queued"
        log.info(f"Task queued: {softurl}")

        batch_id = TASKS[softurl].get("batch_id")
        if batch_id and batch_id in BATCHES:
            BATCHES[batch_id]["a_done"] += 1


# ======================================================
# MAIN SEQUENTIAL LOOP
# ======================================================
async def process_loop():
    global CURRENT_TASK

    while True:
        try:
            if CURRENT_TASK is None and TASK_QUEUE:
                CURRENT_TASK = TASK_QUEUE.pop(0)
                log.info(f"Processing task: {CURRENT_TASK}")

                await userbot.send_message(X_BOT_USERNAME, CURRENT_TASK)
                TASKS[CURRENT_TASK]["state"] = "sent_to_x"

            await asyncio.sleep(1)

        except Exception:
            log.exception("process_loop error")
            await asyncio.sleep(2)


# ======================================================
# X BOT REPLY
# ======================================================
@userbot.on_message(filters.chat(X_BOT_USERNAME))
async def xbot_reply(_, message):
    global CURRENT_TASK

    try:
        if not CURRENT_TASK or not message.text:
            return

        softurl = SOFTURL_REGEX.search(message.text)
        if not softurl or softurl.group() != CURRENT_TASK:
            return

        links = URL_REGEX.findall(message.text)
        A_link = [l for l in links if l != CURRENT_TASK][0]

        log.info(f"Got A-link: {A_link}")

        link_msg = await userbot.send_message(B_BOT_USERNAME, A_link)
        await link_msg.reply("/genlink")

        TASKS[CURRENT_TASK]["state"] = "sent_to_b"

    except Exception:
        log.exception("xbot_reply error")


# ======================================================
# B BOT REPLY
# ======================================================
@userbot.on_message(filters.chat(B_BOT_USERNAME))
async def bbot_reply(_, message):
    global CURRENT_TASK

    try:
        if not CURRENT_TASK or not message.text:
            return

        match = URL_REGEX.search(message.text)
        if not match:
            return

        final_link = match.group()
        log.info(f"B bot returned link: {final_link}")

        if SHORT_URL:
            final_link = await shorten_link(final_link)

        await edit_y_message(CURRENT_TASK, final_link)

        batch_id = TASKS[CURRENT_TASK].get("batch_id")
        if batch_id and batch_id in BATCHES:
            BATCHES[batch_id]["queue_done"] += 1

        TASKS.pop(CURRENT_TASK, None)
        CURRENT_TASK = None

    except Exception:
        log.exception("bbot_reply error")


# ======================================================
# EDIT MESSAGE
# ======================================================
async def edit_y_message(softurl, final_link):
    task = TASKS[softurl]

    msg = await userbot.get_messages(task["y_chat"], task["y_msg_id"])
    text = msg.text or msg.caption

    new_text = text.replace(softurl, final_link)

    try:
        if msg.text:
            await userbot.edit_message_text(task["y_chat"], task["y_msg_id"], new_text)
        else:
            await userbot.edit_message_caption(task["y_chat"], task["y_msg_id"], new_text)

        log.info(f"Edited Y message for {softurl}")

    except MessageNotModified:
        pass

    try:
        await userbot.edit_message_text(
            task["status_chat"],
            task["status_msg"],
            "✅ Processing completed"
        )
    except MessageNotModified:
        pass


# ======================================================
# START
# ======================================================
async def main():
    await userbot.start()
    userbot.loop.create_task(process_loop())
    log.info("Userbot started")
    await asyncio.Event().wait()

asyncio.run(main())