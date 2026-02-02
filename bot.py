import re
import asyncio
import uuid
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from logger import get_logger
from config import API_ID, API_HASH, BOT_TOKEN, Y_GROUP_ID
from shared_store import TASKS, BATCHES
from userbot import process_softurl

log = get_logger("MAIN_BOT")

SOFTURL_REGEX = re.compile(r"https?://softurl\.in/\S+", re.IGNORECASE)

class MainBot(Client):

    async def start(self):
        await super().start()
        log.info("Main bot started")
        self.loop.create_task(self.status_watcher())

    async def status_watcher(self):
        while True:
            try:
                for batch_id, batch in list(BATCHES.items()):
                    if not batch["pending"]:
                        await self.edit_message_text(
                            batch["status_chat"],
                            batch["status_msg"],
                            f"✅ Batch Completed\n\n"
                            f"Total: {batch['total']}\n"
                            f"Forwarded: {batch['forwarded']}\n"
                            f"Edited: {batch['edited']}\n"
                            f"Errors: {batch['errors']}"
                        )
                        BATCHES.pop(batch_id, None)
                await asyncio.sleep(1)
            except Exception:
                log.exception("status_watcher error")
                await asyncio.sleep(2)

app = MainBot(
    "main_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ---------- SINGLE MESSAGE ----------
@app.on_message(filters.private & filters.text & ~filters.command(["batch"]))
async def single_handler(_, message):
    try:
        match = SOFTURL_REGEX.search(message.text)
        if not match:
            return

        softurl = match.group()
        task_id = f"{softurl}:{message.id}"

        copied = await app.copy_message(Y_GROUP_ID, message.chat.id, message.id)
        status = await message.reply("⏳ Processing started...")

        TASKS[task_id] = {
            "softurl": softurl,
            "y_chat": Y_GROUP_ID,
            "y_msg": copied.id,
            "status_chat": message.chat.id,
            "status_msg": status.id,
            "batch_id": None
        }

        asyncio.create_task(process_softurl(task_id, softurl))

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception:
        log.exception("single_handler error")

# ---------- BATCH ----------
@app.on_message(filters.private & filters.command("batch"))
async def batch_handler(_, message):
    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.reply("❌ Usage:\n/batch first_msg_link last_msg_link")
            return

        def parse(link):
            link = link.split("?")[0]
            p = link.rstrip("/").split("/")
            return p[-2], int(p[-1])

        chat, first_id = parse(parts[1])
        _, last_id = parse(parts[2])

        if first_id > last_id:
            first_id, last_id = last_id, first_id

        batch_id = uuid.uuid4().hex[:8]
        status = await message.reply("📦 Batch started...")

        BATCHES[batch_id] = {
            "total": 0,
            "forwarded": 0,
            "edited": 0,
            "errors": 0,
            "pending": set(),
            "status_chat": message.chat.id,
            "status_msg": status.id
        }

        for msg_id in range(first_id, last_id + 1):
            try:
                msg = await app.get_messages(chat, msg_id)
                if not msg:
                    continue

                text = msg.text or msg.caption
                if not text:
                    continue

                match = SOFTURL_REGEX.search(text)
                if not match:
                    continue

                softurl = match.group()
                task_id = f"{softurl}:{msg_id}"

                copied = await app.copy_message(Y_GROUP_ID, chat, msg_id)

                TASKS[task_id] = {
                    "softurl": softurl,
                    "y_chat": Y_GROUP_ID,
                    "y_msg": copied.id,
                    "batch_id": batch_id
                }

                BATCHES[batch_id]["pending"].add(task_id)
                BATCHES[batch_id]["total"] += 1
                BATCHES[batch_id]["forwarded"] += 1

                asyncio.create_task(process_softurl(task_id, softurl))

            except Exception:
                BATCHES[batch_id]["errors"] += 1

        await app.edit_message_text(
            message.chat.id,
            status.id,
            f"📦 Batch Processing\n\n"
            f"Total: {BATCHES[batch_id]['total']}\n"
            f"Forwarded: {BATCHES[batch_id]['forwarded']}\n"
            f"Edited: 0\nErrors: {BATCHES[batch_id]['errors']}"
        )

    except Exception:
        log.exception("batch_handler error")

app.run()