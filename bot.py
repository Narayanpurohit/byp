import re
import asyncio
import uuid
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, MessageNotModified
from logger import get_logger
from config import API_ID, API_HASH, BOT_TOKEN, Y_GROUP_ID
from shared_store import TASKS, BATCHES
from userbot import add_task

log = get_logger("MAIN_BOT")

SOFTURL_REGEX = re.compile(r"https?://softurl\.in/\S+", re.I)

# ======================================================
# MAIN BOT CLASS
# ======================================================
class MainBot(Client):

    async def start(self):
        await super().start()
        log.info("Main bot started")
        self.loop.create_task(self.status_watcher())

    async def status_watcher(self):
        """Edit status messages every 5 seconds (only if changed)"""
        while True:
            try:
                for batch_id, batch in list(BATCHES.items()):
                    text = (
                        "📦 Batch Processing\n\n"
                        f"Total: {batch['total']}\n"
                        f"A-links collected: {batch['a_done']}\n"
                        f"Queued done: {batch['queue_done']}\n"
                        f"Errors: {batch['errors']}"
                    )

                    # 🔐 edit only if changed
                    if batch.get("last_text") != text:
                        try:
                            await self.edit_message_text(
                                batch["status_chat"],
                                batch["status_msg"],
                                text
                            )
                            batch["last_text"] = text
                        except MessageNotModified:
                            pass

                    # ✅ batch complete
                    if batch["queue_done"] + batch["errors"] >= batch["total"]:
                        BATCHES.pop(batch_id, None)

                await asyncio.sleep(5)

            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception:
                log.exception("status_watcher error")
                await asyncio.sleep(5)


app = MainBot(
    "main_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ======================================================
# SINGLE MESSAGE HANDLER
# ======================================================
@app.on_message(filters.private & filters.text & ~filters.command(["batch"]))
async def single_handler(_, message):
    try:
        match = SOFTURL_REGEX.search(message.text)
        if not match:
            return

        softurl = match.group()

        copied = await app.copy_message(
            Y_GROUP_ID,
            message.chat.id,
            message.id
        )

        status = await message.reply("⏳ Processing started...")

        TASKS[softurl] = {
            "y_msg_id": copied.id,
            "status_chat": message.chat.id,
            "status_msg": status.id,
            "batch_id": None
        }

        asyncio.create_task(add_task(softurl, copied.id))

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception:
        log.exception("single_handler error")


# ======================================================
# BATCH HANDLER
# ======================================================
@app.on_message(filters.private & filters.command("batch"))
async def batch_handler(_, message):
    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.reply("❌ Usage:\n/batch first_msg_link last_msg_link")
            return

        def parse(link):
            p = link.rstrip("/").split("/")
            return p[-2], int(p[-1])

        chat, first_id = parse(parts[1])
        _, last_id = parse(parts[2])

        if first_id > last_id:
            first_id, last_id = last_id, first_id

        batch_id = str(uuid.uuid4())[:8]

        status = await message.reply(
            "📦 Batch Processing\n\n"
            "Total: calculating...\n"
            "A-links collected: 0\n"
            "Queued done: 0\n"
            "Errors: 0"
        )

        BATCHES[batch_id] = {
            "total": last_id - first_id + 1,
            "a_done": 0,
            "queue_done": 0,
            "errors": 0,
            "status_chat": message.chat.id,
            "status_msg": status.id,
            "last_text": None
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

                copied = await app.copy_message(Y_GROUP_ID, chat, msg_id)

                TASKS[softurl] = {
                    "y_msg_id": copied.id,
                    "batch_id": batch_id
                }

                asyncio.create_task(add_task(softurl, copied.id))

            except Exception:
                BATCHES[batch_id]["errors"] += 1

    except Exception:
        log.exception("batch_handler error")


# ======================================================
# START BOT
# ======================================================
app.run()