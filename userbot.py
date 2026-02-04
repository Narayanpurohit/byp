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
# QUEUE LOOP (ONE TASK AT A TIME)
# ======================================================
async def queue_worker():
    log.info("🚀 Queue worker started")

    while True:
        try:
            for softurl, task in list(TASKS.items()):
                if task.get("state") != "pending":
                    continue

                log.info(f"▶ Processing: {softurl}")
                task["state"] = "sent_to_x"

                await userbot.send_message(X_BOT_USERNAME, softurl)
                await wait_for_completion(softurl)
                break

            await asyncio.sleep(1)

        except Exception:
            log.exception("queue_worker error")
            await asyncio.sleep(2)


# ======================================================
# WAIT UNTIL TASK FINISHES
# ======================================================
async def wait_for_completion(softurl):
    while softurl in TASKS:
        await asyncio.sleep(1)


# ======================================================
# X BOT REPLY → A LINK
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
        task = TASKS.get(softurl)
        if not task:
            return

        links = URL_REGEX.findall(message.text)
        A_link = [l for l in links if l != softurl][0]

        task["A_link"] = A_link
        task["state"] = "got_A"

        batch_id = task.get("batch_id")
        if batch_id in BATCHES:
            BATCHES[batch_id]["a_done"] += 1

        msg = await userbot.send_message(B_BOT_USERNAME, A_link)
        await msg.reply("/genlink")

        task["state"] = "sent_to_b"

    except Exception:
        log.exception("xbot_reply error")


# ======================================================
# B BOT REPLY → FINAL LINK
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
                final_link = await shorten_link(new_link)

            await edit_y_message(task, softurl, final_link)

            batch_id = task.get("batch_id")
            if batch_id in BATCHES:
                BATCHES[batch_id]["queue_done"] += 1

            TASKS.pop(softurl, None)
            log.info(f"✅ Task done: {softurl}")
            break

    except Exception:
        log.exception("bbot_reply error")


# ======================================================
# EDIT Y CHAT MESSAGE
# ======================================================
async def edit_y_message(task, softurl, final_link):
    msg = await userbot.get_messages(
        task["y_chat"],
        task["y_msg_id"]
    )

    text = msg.text or msg.caption
    if not text:
        return

    new_text = text.replace(softurl, final_link)

    try:
        if msg.text:
            await userbot.edit_message_text(task["y_chat"], task["y_msg_id"], new_text)
        else:
            await userbot.edit_message_caption(task["y_chat"], task["y_msg_id"], new_text)
    except MessageNotModified:
        pass


# ======================================================
# START
# ======================================================
async def main():
    await userbot.start()
    asyncio.create_task(queue_worker())
    await asyncio.Event().wait()

asyncio.run(main())