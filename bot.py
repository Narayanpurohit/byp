import re
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from logger import get_logger
from config import API_ID, API_HASH, BOT_TOKEN, Y_GROUP_ID
from userbot import process_softurl
from shared_store import TASKS

log = get_logger("MAIN_BOT")

SOFTURL_REGEX = re.compile(r"https?://softurl\.in/\S+", re.IGNORECASE)

app = Client(
    "main_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@app.on_message(filters.private)
async def handler(_, message):
    try:
        text = message.text or message.caption
        if not text:
            return

        match = SOFTURL_REGEX.search(text)
        if not match:
            await message.reply("❌ softurl.in link nahi mila.")
            return

        softurl = match.group()

        # 1️⃣ copy msg to Y group
        copied = await app.copy_message(
            chat_id=Y_GROUP_ID,
            from_chat_id=message.chat.id,
            message_id=message.id
        )

        # 2️⃣ send status msg
        status = await message.reply("⏳ Processing started...")

        # 3️⃣ store task
        TASKS[softurl] = {
            "y_chat": Y_GROUP_ID,
            "y_msg": copied.id,
            "status_chat": message.chat.id,
            "status_msg": status.id,
            "state": "processing",
            "error": None
        }

        # 4️⃣ send to userbot
        asyncio.create_task(process_softurl(softurl))

        log.info(f"Task created for {softurl}")

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception:
        log.exception("bot handler error")

# 🔁 background watcher: edits status based on TASKS
async def status_watcher():
    while True:
        try:
            for softurl, task in list(TASKS.items()):
                if task["state"] == "done":
                    await app.edit_message_text(
                        task["status_chat"],
                        task["status_msg"],
                        "✅ Done! Message updated successfully"
                    )
                    TASKS.pop(softurl, None)

                elif task["state"] == "error":
                    await app.edit_message_text(
                        task["status_chat"],
                        task["status_msg"],
                        f"❌ Error:\n{task['error']}"
                    )
                    TASKS.pop(softurl, None)

            await asyncio.sleep(1)

        except Exception:
            log.exception("status_watcher error")
            await asyncio.sleep(2)

@app.on_start()
async def start_bg_tasks():
    asyncio.create_task(status_watcher())

app.run()