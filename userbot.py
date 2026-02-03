import re
import asyncio
from collections import deque
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from config import (
    API_ID,
    API_HASH,
    SESSION_STRING,
    X_BOT_USERNAME,
    B_BOT_USERNAME,
    Y_GROUP_ID,
)
from shortner import shorten_link
from logger import get_logger

log = get_logger("USERBOT")

# ---------- REGEX ----------
SOFTURL_REGEX = re.compile(r"https?://softurl\.in/\S+", re.I)
URL_REGEX = re.compile(r"https?://\S+")

# ---------- CLIENT ----------
userbot = Client(
    "userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# ---------- MEMORY ----------
TASKS = {}          # softurl -> task
QUEUE = deque()     # task_ids in order
QUEUE_RUNNING = False


# ---------- TASK STRUCT ----------
def new_task(softurl, y_msg_id):
    return {
        "softurl": softurl,
        "A_link": None,
        "final_link": None,
        "y_msg_id": y_msg_id,
        "state": "waiting_for_A"   # waiting_for_A → ready → done
    }


# =========================================================
# PHASE 1 — PARALLEL (X BOT)
# =========================================================
async def send_to_xbot(softurl: str):
    try:
        await userbot.send_message(X_BOT_USERNAME, softurl)
        log.info(f"Sent to X bot: {softurl}")
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await send_to_xbot(softurl)


@userbot.on_message(filters.chat(X_BOT_USERNAME))
async def xbot_reply(_, message):
    if not message.text:
        return

    soft_match = SOFTURL_REGEX.search(message.text)
    if not soft_match:
        return

    softurl = soft_match.group()
    if softurl not in TASKS:
        return

    links = URL_REGEX.findall(message.text)
    A_link = next((l for l in links if l != softurl), None)
    if not A_link:
        return

    TASKS[softurl]["A_link"] = A_link
    TASKS[softurl]["state"] = "ready"

    log.info(f"A link stored for {softurl}")

    # check if ALL tasks are ready
    if all(t["state"] == "ready" for t in TASKS.values()):
        asyncio.create_task(start_queue())


# =========================================================
# PHASE 2 — QUEUE (B BOT + EDIT)
# =========================================================
async def start_queue():
    global QUEUE_RUNNING
    if QUEUE_RUNNING:
        return

    QUEUE_RUNNING = True
    log.info("Queue started")

    while QUEUE:
        softurl = QUEUE.popleft()
        task = TASKS.get(softurl)
        if not task:
            continue

        try:
            # ---- send A link to B bot
            await userbot.send_message(B_BOT_USERNAME, task["A_link"])
            await userbot.send_message(B_BOT_USERNAME, "/genlink")

            # wait for B bot reply
            final = await wait_bbot_reply()
            short = await shorten_link(final)

            # edit Y message
            msg = await userbot.get_messages(Y_GROUP_ID, task["y_msg_id"])
            text = msg.text or msg.caption
            new_text = text.replace(task["softurl"], short)

            if msg.text:
                await userbot.edit_message_text(Y_GROUP_ID, msg.id, new_text)
            else:
                await userbot.edit_message_caption(Y_GROUP_ID, msg.id, new_text)

            task["state"] = "done"
            log.info(f"Completed: {softurl}")

        except Exception:
            log.exception("Queue task failed")

    QUEUE_RUNNING = False
    TASKS.clear()
    log.info("Queue finished")


# ---------- wait B bot reply ----------
async def wait_bbot_reply(timeout=60):
    fut = asyncio.get_event_loop().create_future()

    @userbot.on_message(filters.chat(B_BOT_USERNAME))
    async def _bbot(_, msg):
        if msg.text:
            link = URL_REGEX.search(msg.text)
            if link and not fut.done():
                fut.set_result(link.group())

    return await asyncio.wait_for(fut, timeout)


# =========================================================
# ENTRY POINT (called by main bot)
# =========================================================
async def add_task(softurl: str, y_msg_id: int):
    if softurl in TASKS:
        return

    TASKS[softurl] = new_task(softurl, y_msg_id)
    QUEUE.append(softurl)

    # Phase-1 parallel trigger
    asyncio.create_task(send_to_xbot(softurl))


# =========================================================
# START
# =========================================================
userbot.start()
log.info("Userbot started")