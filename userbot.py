import json
import re
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from config import *
from shortner import shorten_link

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | USERBOT | %(levelname)s | %(message)s"
)
log = logging.getLogger(__name__)

user = Client(
    "userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

URL_REGEX = re.compile(r"https?://\S+")

EXPECTED_C = 0
PROCESSING_STARTED = False
STATUS_CTX = {}

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

# ---------------- STATUS UPDATE ----------------
async def update_status(bot):
    tasks = load_tasks()
    await bot.edit_message_text(
        STATUS_CTX["chat"],
        STATUS_CTX["msg"],
        f"""
📦 Batch Status

C links total : {EXPECTED_C}
A links ready : {sum(1 for t in tasks.values() if t["A"])}
Processed     : {STATUS_CTX["done"]}
Errors        : {STATUS_CTX["errors"]}
"""
    )

# ---------------- X BOT HANDLER ----------------
@user.on_message(filters.chat(X_BOT_USERNAME) & filters.reply)
async def xbot_reply(_, message):
    global PROCESSING_STARTED

    reply = message.reply_to_message.text or ""
    text = message.text or ""

    reply_links = URL_REGEX.findall(reply)
    msg_links = URL_REGEX.findall(text)

    if not reply_links or not msg_links:
        return

    c_link = reply_links[0]
    a_link = msg_links[-1]

    tasks = load_tasks()
    if c_link not in tasks or tasks[c_link]["A"]:
        return

    tasks[c_link]["A"] = a_link
    save_tasks(tasks)

    log.info(f"A stored | {c_link}")

    if sum(1 for t in tasks.values() if t["A"]) == EXPECTED_C:
        if not PROCESSING_STARTED:
            PROCESSING_STARTED = True
            asyncio.create_task(process_all_links())

# ---------------- PHASE 2 ----------------
async def process_all_links():
    log.info("All A links collected → starting processing phase")

    tasks = load_tasks()
    for c_link, data in list(tasks.items()):
        try:
            sent = await user.send_message(B_BOT_USERNAME, data["A"])
            await sent.reply("/genlink")

            async for r in user.get_chat_history(B_BOT_USERNAME, limit=5):
                if r.text and "http" in r.text:
                    b_link = r.text
                    short = await shorten_link(b_link)

                    await bot.edit_message_text(
                        Y_CHAT_ID,
                        data["msg_id"],
                        short
                    )

                    tasks = load_tasks()
                    tasks.pop(c_link, None)
                    save_tasks(tasks)

                    STATUS_CTX["done"] += 1
                    await update_status(bot)

                    log.info(f"Completed | {c_link}")
                    break

        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            STATUS_CTX["errors"] += 1
            log.exception(f"Failed | {c_link}")

# ---------------- PHASE 1 ----------------
async def start_batch_userbot(
    bot,
    chat,
    first_id,
    last_id,
    status_chat,
    status_msg,
    batch_id
):
    global EXPECTED_C, PROCESSING_STARTED, STATUS_CTX

    await user.start()
    save_tasks({})
    EXPECTED_C = 0
    PROCESSING_STARTED = False

    STATUS_CTX = {
        "chat": status_chat,
        "msg": status_msg,
        "done": 0,
        "errors": 0
    }

    for msg_id in range(first_id, last_id + 1):
        try:
            msg = await user.get_messages(chat, msg_id)
            if not msg:
                continue

            text = msg.text or msg.caption or ""
            c_links = [l for l in URL_REGEX.findall(text) if C_DOMAIN in l]
            if not c_links:
                continue

            copied = await bot.copy_message(Y_CHAT_ID, chat, msg_id)

            tasks = load_tasks()
            for c in c_links:
                tasks[c] = {
                    "msg_id": copied.id,
                    "A": ""
                }
                EXPECTED_C += 1
                await user.send_message(X_BOT_USERNAME, c)

            save_tasks(tasks)
            await update_status(bot)

        except Exception:
            STATUS_CTX["errors"] += 1

    log.info(f"Phase 1 done | waiting for {EXPECTED_C} A links")