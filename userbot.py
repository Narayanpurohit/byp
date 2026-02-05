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

STATUS_CTX = {
    "total": 0,
    "a_ready": 0,
    "done": 0,
    "errors": 0
}

PROCESSING_STARTED = False

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

# ---------------- X BOT HANDLER ----------------
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

    if STATUS_CTX["a_ready"] == STATUS_CTX["total"] and not PROCESSING_STARTED:
        PROCESSING_STARTED = True
        asyncio.create_task(process_all_links())

# ---------------- PHASE 2 ----------------
async def process_all_links():
    log.info("Processing phase started")

    tasks = load_tasks()

    for c_link, data in list(tasks.items()):
        try:
            # 1️⃣ Send A → B bot
            sent = await user.send_message(B_BOT_USERNAME, data["A"])
            await sent.reply("/genlink")

            # 2️⃣ Wait for B bot reply
            async for r in user.get_chat_history(B_BOT_USERNAME, limit=5):
                if not r.text or "http" not in r.text:
                    continue

                b_link = r.text.strip()
                short = await shorten_link(b_link)

                # 3️⃣ FETCH CURRENT MESSAGE FROM Y_CHAT_ID
                msg = await user.get_messages(Y_CHAT_ID, data["msg_id"])
                current_text = msg.caption if msg.caption is not None else msg.text

                if not current_text:
                    raise Exception("Message has no editable text")

                # 4️⃣ REPLACE ONLY C LINK
                if c_link in current_text:
                    new_text = current_text.replace(c_link, short)
                else:
                    new_text = current_text + f"\n\n{short}"

                # 5️⃣ EDIT MESSAGE (text / caption auto)
                if msg.caption is not None:
                    await user.edit_message_caption(
                        Y_CHAT_ID,
                        data["msg_id"],
                        new_text
                    )
                else:
                    await user.edit_message_text(
                        Y_CHAT_ID,
                        data["msg_id"],
                        new_text
                    )

                # 6️⃣ CLEANUP
                tasks = load_tasks()
                tasks.pop(c_link, None)
                save_tasks(tasks)

                STATUS_CTX["done"] += 1
                log.info(f"Completed | {c_link}")
                break

        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            STATUS_CTX["errors"] += 1
            log.exception(f"Failed | {c_link}")

# ---------------- PHASE 1 ----------------
async def start_batch_userbot(chat, first_id, last_id, batch_id):
    global PROCESSING_STARTED

    await user.start()
    save_tasks({})
    PROCESSING_STARTED = False

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

            copied = await user.copy_message(
                Y_CHAT_ID,
                chat,
                msg_id
            )

            tasks = load_tasks()
            for c in c_links:
                tasks[c] = {
                    "msg_id": copied.id,
                    "A": ""
                }
                STATUS_CTX["total"] += 1
                await user.send_message(X_BOT_USERNAME, c)

            save_tasks(tasks)

        except Exception:
            STATUS_CTX["errors"] += 1

    log.info(f"Phase 1 done | waiting for {STATUS_CTX['total']} A links")