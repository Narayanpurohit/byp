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

TASK_QUEUE = []        # 🔑 real queue
CURRENT_TASK = None   # jo abhi process ho raha

userbot = Client(
    "userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# ======================================================
# ENTRY POINT (called from main bot)
# ======================================================
async def add_task(softurl, y_msg_id):
    task = TASKS.get(softurl)
    if not task:
        return

    if softurl not in TASK_QUEUE:
        TASK_QUEUE.append(softurl)
        task["state"] = "queued"
        log.info(f"Queued task: {softurl}")

        batch_id = task.get("batch_id")
        if batch_id and batch_id in BATCHES:
            BATCHES[batch_id]["a_done"] += 1


# ======================================================
# MAIN PROCESS LOOP (SEQUENTIAL WORKER)
# ======================================================
async def process_loop():
    global CURRENT_TASK

    while True:
        try:
            if CURRENT_TASK is None and TASK_QUEUE:
                CURRENT_TASK = TASK_QUEUE.pop(0)
                task = TASKS.get(CURRENT_TASK)

                if not task:
                    CURRENT_TASK = None
                    continue

                await userbot.send_message(X_BOT_USERNAME, CURRENT_TASK)
                task["state"] = "sent_to_x"
                log.info(f"Sent to X bot: {CURRENT_TASK}")

            await asyncio.sleep(1)

        except Exception:
            log.exception("process_loop error")
            await asyncio.sleep(2)


# ======================================================
# X BOT REPLY → extract A link
# ======================================================
@userbot.on_message(filters.chat(X_BOT_USERNAME))
async def xbot_reply(_, message):
    global CURRENT_TASK

    try:
        if not CURRENT_TASK or not message.text:
            return

        soft_match = SOFTURL_REGEX.search(message.text)
        if not soft_match:
            return

        softurl = soft_match.group()
        if softurl != CURRENT_TASK:
            return

        links = URL_REGEX.findall(message.text)
        if len(links) < 2:
            return

        A_link = [l for l in links if l != softurl][0]

        TASKS[softurl]["A_link"] = A_link
        TASKS[softurl]["state"] = "got_A"

        # send A link to B bot
        link_msg = await userbot.send_message(B_BOT_USERNAME, A_link)
        await link_msg.reply("/genlink")

        TASKS[softurl]["state"] = "sent_to_b"
        log.info("A link sent to B bot")

    except Exception:
        log.exception("xbot_reply error")


# ======================================================
# B BOT REPLY (DIRECT MESSAGE)
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

        new_link = match.group()
        final_link = new_link

        if SHORT_URL:
            try:
                final_link = await shorten_link(new_link)
            except Exception:
                pass

        await edit_y_message(CURRENT_TASK, final_link)

        task = TASKS.get(CURRENT_TASK)
        if task:
            batch_id = task.get("batch_id")
            if batch_id and batch_id in BATCHES:
                BATCHES[batch_id]["queue_done"] += 1

        TASKS.pop(CURRENT_TASK, None)
        CURRENT_TASK = None   # 🔁 allow next task

    except Exception:
        log.exception("bbot_reply error")


# ======================================================
# EDIT MESSAGE IN Y CHAT + STATUS UPDATE
# ======================================================
async def edit_y_message(softurl, final_link):
    task = TASKS[softurl]

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

    try:
        await userbot.edit_message_text(
            task["status_chat"],
            task["status_msg"],
            "✅ Processing completed"
        )
    except MessageNotModified:
        pass


# ======================================================
# START USERBOT
# ======================================================
async def main():
    await userbot.start()
    userbot.loop.create_task(process_loop())
    log.info("Userbot started with sequential queue")
    await asyncio.Event().wait()

asyncio.run(main())