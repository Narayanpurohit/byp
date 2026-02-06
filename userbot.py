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

USERBOT_STARTED = False
PROCESSING_STARTED = False

# ---------------- CONSTANTS ----------------

URL_REGEX = re.compile(r"https?://\S+")

STATUS_CTX = {
    "total": 0,
    "a_ready": 0,
    "done": 0,
    "errors": 0
}

# ---------------- SAFE START ----------------

async def safe_start_userbot():
    global USERBOT_STARTED
    if USERBOT_STARTED:
        return
    await user.start()
    USERBOT_STARTED = True
    log.info("Userbot started")

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

# ---------------- X BOT HANDLER (A LINK) ----------------

@user.on_message(filters.chat(X_BOT_USERNAME) & filters.reply)
async def xbot_reply(_, message):
    global PROCESSING_STARTED

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
    save_tasks(tasks)

    STATUS_CTX["a_ready"] += 1
    log.info(f"A stored | {c_link}")

    # 🔥 AUTO START B PHASE ONLY WHEN ALL A READY
    if STATUS_CTX["a_ready"] == STATUS_CTX["total"] and not PROCESSING_STARTED:
        PROCESSING_STARTED = True
        asyncio.create_task(start_b_phase())

# ---------------- PHASE 2 (A → B BOT) ----------------

async def start_b_phase():
    await safe_start_userbot()
    log.info("B-bot phase started")

    tasks = load_tasks()

    for c_link, data in tasks.items():
        if not data.get("A") or data.get("B"):
            continue

        try:
            sent = await user.send_message(B_BOT_USERNAME, data["A"])
            await sent.reply("/genlink")
            await asyncio.sleep(2)
        except Exception:
            STATUS_CTX["errors"] += 1
            log.exception(f"A → B failed | {c_link}")

# ---------------- B BOT HANDLER (B LINK) ----------------

@user.on_message(filters.chat(B_BOT_USERNAME) & filters.reply)
async def bbot_reply(_, message):
    try:
        text = message.text or ""
        links = URL_REGEX.findall(text)
        if not links:
            return

        b_link = links[-1]

        reply = message.reply_to_message
        if not reply or not reply.text:
            return

        a_link = reply.text.strip()
        tasks = load_tasks()

        target_c = None
        for c, d in tasks.items():
            if d.get("A") == a_link and not d.get("B"):
                target_c = c
                break

        if not target_c:
            return

        tasks[target_c]["B"] = b_link
        save_tasks(tasks)

        log.info(f"B stored | {target_c}")
        asyncio.create_task(finalize_task(target_c))

    except Exception:
        STATUS_CTX["errors"] += 1
        log.exception("B bot handler failed")

# ---------------- FINAL PROCESS ----------------

async def finalize_task(c_link):
    try:
        await safe_start_userbot()

        tasks = load_tasks()
        data = tasks.get(c_link)
        if not data or not data.get("B"):
            return

        short = await shorten_link(data["B"])

        msg = await user.get_messages(Y_CHAT_ID, data["msg_id"])
        current = msg.caption if msg.caption else msg.text
        if not current:
            return

        # ✅ ONLY REPLACE C LINK
        if c_link in current:
            new_text = current.replace(c_link, short)
        else:
            new_text = current + f"\n\n{short}"

        if msg.caption:
            await user.edit_message_caption(Y_CHAT_ID, data["msg_id"], new_text)
        else:
            await user.edit_message_text(Y_CHAT_ID, data["msg_id"], new_text)

        tasks.pop(c_link, None)
        save_tasks(tasks)

        STATUS_CTX["done"] += 1
        log.info(f"Completed | {c_link}")

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception:
        STATUS_CTX["errors"] += 1
        log.exception(f"Finalize failed | {c_link}")

# ---------------- PHASE 1 (C LINK COLLECT) ----------------

async def start_batch_userbot(chat, first_id, last_id, batch_id):
    global PROCESSING_STARTED

    await safe_start_userbot()
    PROCESSING_STARTED = False
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
                    "B": ""
                }
                c= "B "+c
                STATUS_CTX["total"] += 1
                await user.send_message(X_BOT_USERNAME, c)

            save_tasks(tasks)

        except Exception:
            STATUS_CTX["errors"] += 1
            log.exception("Phase 1 error")