# userbot.py
import re
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import MessageNotModified
from logger import get_logger
from config import (
    API_ID, API_HASH, SESSION_STRING,
    X_BOT_USERNAME, B_BOT_USERNAME, SHORT_URL
)
from shared_store import TASKS, BATCHES
from shortner import shorten_link

log = get_logger("USERBOT")

SOFTURL_REGEX = re.compile(r"https?://softurl\.in/\S+", re.I)
URL_REGEX = re.compile(r"https?://\S+")

TASK_QUEUE = []
CURRENT = None

userbot = Client(
    "userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# ======================================================
# ADD TASK FROM BOT
# ======================================================
async def add_task(softurl, _):
    if softurl not in TASK_QUEUE:
        TASK_QUEUE.append(softurl)
        log.info(f"Queued: {softurl}")

        batch_id = TASKS[softurl].get("batch_id")
        if batch_id in BATCHES:
            BATCHES[batch_id]["a_done"] += 1


# ======================================================
# MAIN QUEUE LOOP
# ======================================================
async def queue_loop():
    global CURRENT

    while True:
        if CURRENT is None and TASK_QUEUE:
            CURRENT = TASK_QUEUE.pop(0)
            log.info(f"Processing: {CURRENT}")
            await userbot.send_message(X_BOT_USERNAME, CURRENT)

        await asyncio.sleep(1)


# ======================================================
# X BOT REPLY
# ======================================================
@userbot.on_message(filters.chat(X_BOT_USERNAME))
async def xbot_reply(_, message):
    global CURRENT
    if not CURRENT or not message.text:
        return

    if CURRENT not in message.text:
        return

    links = URL_REGEX.findall(message.text)
    A_link = [l for l in links if l != CURRENT][0]
    log.info(f"A link: {A_link}")

    msg = await userbot.send_message(B_BOT_USERNAME, A_link)
    await msg.reply("/genlink")


# ======================================================
# B BOT REPLY
# ======================================================
@userbot.on_message(filters.chat(B_BOT_USERNAME))
async def bbot_reply(_, message):
    global CURRENT
    if not CURRENT or not message.text:
        return

    match = URL_REGEX.search(message.text)
    if not match:
        return

    final = match.group()
    if SHORT_URL:
        final = await shorten_link(final)

    task = TASKS[CURRENT]
    msg = await userbot.get_messages(task["y_chat"], task["y_msg_id"])
    text = (msg.text or msg.caption).replace(CURRENT, final)

    try:
        if msg.text:
            await userbot.edit_message_text(task["y_chat"], task["y_msg_id"], text)
        else:
            await userbot.edit_message_caption(task["y_chat"], task["y_msg_id"], text)
    except MessageNotModified:
        pass

    batch_id = task.get("batch_id")
    if batch_id in BATCHES:
        BATCHES[batch_id]["queue_done"] += 1

    log.info(f"Done: {CURRENT}")
    TASKS.pop(CURRENT)
    CURRENT = None


# ======================================================
# START
# ======================================================
async def main():
    await userbot.start()
    userbot.loop.create_task(queue_loop())
    log.info("Userbot started (BATCH ONLY)")
    await asyncio.Event().wait()

asyncio.run(main())