import re
import asyncio
import uuid
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, MessageNotModified
from logger import get_logger
from config import API_ID, API_HASH, BOT_TOKEN, Y_GROUP_ID
from shared_store import TASKS, BATCHES

log = get_logger("MAIN_BOT")

SOFTURL_REGEX = re.compile(r"https?://softurl\.in/\S+", re.I)


class MainBot(Client):

    async def start(self):
        await super().start()
        log.info("✅ Main bot started")
        self.loop.create_task(self.status_watcher())

    async def status_watcher(self):
        while True:
            try:
                for batch_id, batch in list(BATCHES.items()):
                    text = (
                        "📦 Batch Processing\n\n"
                        f"Total: {batch['total']}\n"
                        f"A-links collected: {batch['a_done']}\n"
                        f"Queue done: {batch['queue_done']}\n"
                        f"Errors: {batch['errors']}"
                    )

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

                    if batch["queue_done"] + batch["errors"] >= batch["total"]:
                        log.info(f"✅ Batch {batch_id} completed")
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
# ADD TASK (QUEUE ENTRY POINT)
# ======================================================
async def add_task(softurl):
    task = TASKS.get(softurl)
    if not task:
        return
    task["state"] = "pending"
    log.info(f"📌 Task queued: {softurl}")


# ======================================================
# BATCH HANDLER (ONLY MODE)
# ======================================================
@app.on_message(filters.private & filters.command("batch"))
async def batch_handler(_, message):
    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.reply("❌ /batch first_link last_link")
            return

        def parse(link):
            p = link.rstrip("/").split("/")
            return p[-2], int(p[-1])

        chat, first_id = parse(parts[1])
        _, last_id = parse(parts[2])
        if first_id > last_id:
            first_id, last_id = last_id, first_id

        batch_id = str(uuid.uuid4())[:8]

        status = await message.reply("📦 Batch starting...")

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
                    "y_chat": Y_GROUP_ID,
                    "y_msg_id": copied.id,
                    "batch_id": batch_id,
                    "state": "new"
                }

                await add_task(softurl)

            except Exception:
                BATCHES[batch_id]["errors"] += 1

    except Exception:
        log.exception("batch_handler error")


app.run()