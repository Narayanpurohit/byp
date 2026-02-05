import json
import re
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from config import *
from shortner import shorten_link

# ---------------- LOGGING ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | USERBOT | %(levelname)s | %(message)s"
)
log = logging.getLogger(__name__)

# ---------------- CLIENT ----------------
user = Client(
    "userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

URL_REGEX = re.compile(r"https?://\S+")

# ---------------- STATUS (BOT READS) ----------------
STATUS_CTX = {
    "total": 0,
    "a_ready": 0,
    "done": 0,
    "errors": 0
}

# ---------------- FLAGS ----------------
CURRENT_PROCESSING = None          # c_link
PROCESS_LOCK = asyncio.Lock()
PROCESS_TIMEOUT_TASK = None        # asyncio.Task

TIMEOUT_SECONDS = 20

# ---------------- JSON ----------------
def load_tasks():
    try:
        with open("tasks.json", "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_tasks(data):
    with open("tasks.json", "w") as f:
        json.dump(data, f, indent=2)

# ---------------- START NEXT PROCESS ----------------
async def start_next_process():
    global CURRENT_PROCESSING, PROCESS_TIMEOUT_TASK

    async with PROCESS_LOCK:
        if CURRENT_PROCESSING is not None:
            return

        tasks = load_tasks()
        for c_link, data in tasks.items():
            if data.get("state") == "READY":
                CURRENT_PROCESSING = c_link
                data["state"] = "PROCESSING"
                save_tasks(tasks)

                log.info(f"▶ Processing started | {c_link}")

                sent = await user.send_message(B_BOT_USERNAME, data["A"])
                await sent.reply("/genlink")

                PROCESS_TIMEOUT_TASK = asyncio.create_task(
                    processing_timeout(c_link)
                )
                return

# ---------------- TIMEOUT HANDLER ----------------
async def processing_timeout(c_link):
    global CURRENT_PROCESSING

    await asyncio.sleep(TIMEOUT_SECONDS)

    if CURRENT_PROCESSING != c_link:
        return

    log.error(f"⏱ Timeout | {c_link}")

    tasks = load_tasks()
    if c_link in tasks:
        tasks[c_link]["state"] = "READY"
        save_tasks(tasks)

    CURRENT_PROCESSING = None
    STATUS_CTX["errors"] += 1

    await start_next_process()

# ---------------- X BOT HANDLER (A LINK) ----------------
@user.on_message(filters.chat(X_BOT_USERNAME) & filters.reply)
async def xbot_reply(_, message):
    reply_text = message.reply_to_message.text or ""
    text = message.text or ""

    reply_links = URL_REGEX.findall(reply_text)
    msg_links = URL_REGEX.findall(text)

    if not reply_links or not msg_links:
        return

    c_link = reply_links[0]
    a_link = msg_links[-1]

    tasks = load_tasks()
    if c_link not in tasks or tasks[c_link]["A"]:
        return

    tasks[c_link]["A"] = a_link
    tasks[c_link]["state"] = "READY"
    save_tasks(tasks)

    STATUS_CTX["a_ready"] += 1
    log.info(f"A stored | {c_link}")

    if STATUS_CTX["a_ready"] == STATUS_CTX["total"]:
        await start_next_process()

# ---------------- B BOT EDIT HANDLER ----------------
@user.on_message(filters.chat(B_BOT_USERNAME) & filters.edited)
async def bbot_edited(_, message):
    global CURRENT_PROCESSING, PROCESS_TIMEOUT_TASK

    if CURRENT_PROCESSING is None:
        return

    if not message.text or "http" not in message.text:
        return

    b_link = message.text.strip()
    c_link = CURRENT_PROCESSING

    try:
        short = await shorten_link(b_link)

        tasks = load_tasks()
        data = tasks.get(c_link)
        if not data:
            return

        msg = await user.get_messages(Y_CHAT_ID, data["msg_id"])
        current_text = msg.caption if msg.caption else msg.text
        if not current_text:
            raise Exception("No editable text")

        new_text = (
            current_text.replace(c_link, short)
            if c_link in current_text
            else current_text + f"\n\n{short}"
        )

        if msg.caption:
            await user.edit_message_caption(Y_CHAT_ID, msg.id, new_text)
        else:
            await user.edit_message_text(Y_CHAT_ID, msg.id, new_text)

        tasks.pop(c_link, None)
        save_tasks(tasks)

        STATUS_CTX["done"] += 1
        log.info(f"✅ Completed | {c_link}")

    except Exception:
        STATUS_CTX["errors"] += 1
        log.exception("Finalize failed")

    finally:
        if PROCESS_TIMEOUT_TASK:
            PROCESS_TIMEOUT_TASK.cancel()
            PROCESS_TIMEOUT_TASK = None

        CURRENT_PROCESSING = None
        await start_next_process()

# ---------------- PHASE 1 (COLLECT C LINKS) ----------------
async def start_batch_userbot(chat, first_id, last_id, batch_id):
    await user.start()
    save_tasks({})

    STATUS_CTX.update({
        "total": 0,
        "a_ready": 0,
        "done": 0,
        "errors": 0
    })

    for msg_id in range(first_id, last_id + 1):
        try:
            msg = await user.get_messages(chat, msg_id)
            if not msg:
                continue

            text = msg.text or msg.caption or ""
            c_links = [l for l in URL_REGEX.findall(text) if C_DOMAIN in l]
            if not c_links:
                continue

            copied = await user.copy_message(Y_CHAT_ID, chat, msg_id)

            tasks = load_tasks()
            for c in c_links:
                tasks[c] = {
                    "msg_id": copied.id,
                    "A": "",
                    "state": "PENDING"
                }
                STATUS_CTX["total"] += 1
                await user.send_message(X_BOT_USERNAME, c)

            save_tasks(tasks)

        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            STATUS_CTX["errors"] += 1

    log.info(f"📦 Phase-1 done | Waiting for {STATUS_CTX['total']} A links")