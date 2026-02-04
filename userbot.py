import json
import re
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from config import *
from shortner import shorten_link

# -------------------------------------------------
# USERBOT CLIENT
# -------------------------------------------------
user = Client(
    "userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# -------------------------------------------------
# REGEX
# -------------------------------------------------
URL_REGEX = re.compile(r"https?://\S+")

# -------------------------------------------------
# JSON HELPERS
# -------------------------------------------------
def load_tasks():
    try:
        with open("tasks.json", "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_tasks(data):
    with open("tasks.json", "w") as f:
        json.dump(data, f, indent=2)

# -------------------------------------------------
# X BOT REPLY HANDLER (C LINK -> A LINK)
# -------------------------------------------------
@user.on_message(filters.chat(X_BOT_USERNAME) & filters.reply)
async def x_bot_reply_handler(_, message):
    try:
        reply_text = message.reply_to_message.text or ""
        text = message.text or ""

        reply_links = URL_REGEX.findall(reply_text)
        msg_links = URL_REGEX.findall(text)

        if not reply_links or not msg_links:
            return

        c_link = reply_links[0]
        a_link = msg_links[-1]

        tasks = load_tasks()
        if c_link in tasks and not tasks[c_link]["A"]:
            tasks[c_link]["A"] = a_link
            save_tasks(tasks)

    except Exception:
        pass

# -------------------------------------------------
# MAIN BATCH WORKER
# -------------------------------------------------
async def start_batch_userbot(
    bot,
    chat,
    first_id,
    last_id,
    status_chat,
    status_msg,
    batch_id
):
    await user.start()

    tasks = load_tasks()
    total = last_id - first_id + 1

    processed = 0
    errors = 0

    # ---------------- FETCH & COPY MESSAGES ----------------
    for msg_id in range(first_id, last_id + 1):
        try:
            msg = await user.get_messages(chat, msg_id)
            if not msg:
                continue

            text = msg.text or msg.caption
            if not text:
                continue

            links = URL_REGEX.findall(text)
            c_links = [l for l in links if C_DOMAIN in l]

            if not c_links:
                continue

            copied = await bot.copy_message(
                Y_CHAT_ID,
                chat,
                msg_id
            )

            for c in c_links:
                tasks[c] = {
                    "msg_id": copied.id,
                    "A": "",
                    "B": "",
                    "short": "",
                    "batch": batch_id
                }

                await user.send_message(X_BOT_USERNAME, c)

            processed += 1

        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            errors += 1

        save_tasks(tasks)

        # status update
        await bot.edit_message_text(
            status_chat,
            status_msg,
            f"""
📦 **Batch Processing**

Total messages : {total}
Processed      : {processed}
Errors         : {errors}
A-links found  : {sum(1 for t in tasks.values() if t["A"])}
"""
        )

    # ---------------- PROCESS B BOT ----------------
    for c_link, data in list(tasks.items()):
        if not data["A"]:
            continue

        try:
            sent = await user.send_message(B_BOT_USERNAME, data["A"])
            await sent.reply("/genlink")

            async for r in user.get_chat_history(B_BOT_USERNAME, limit=5):
                if r.text and "http" in r.text:
                    data["B"] = r.text
                    data["short"] = await shorten_link(r.text)

                    await bot.edit_message_text(
                        Y_CHAT_ID,
                        data["msg_id"],
                        data["short"]
                    )

                    del tasks[c_link]
                    save_tasks(tasks)
                    break

        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            errors += 1

    # ---------------- FINAL STATUS ----------------
    await bot.edit_message_text(
        status_chat,
        status_msg,
        "✅ **Batch Completed Successfully**"
    )