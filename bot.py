import os
import asyncio
import logging
import uuid
from pyrogram import Client, filters
from config import *
from userbot import start_batch_userbot, STATUS_CTX,start_b_phase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | BOT | %(levelname)s | %(message)s"
)
log = logging.getLogger(__name__)

bot = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

LAST_STATUS_TEXT = None

async def status_watcher(chat_id, msg_id):
    global LAST_STATUS_TEXT

    while True:
        await asyncio.sleep(5)

        status_text = (
            "📦 Batch Status\n\n"
            f"C links total : {STATUS_CTX['total']}\n"
            f"A links ready : {STATUS_CTX['a_ready']}\n"
            f"Processed     : {STATUS_CTX['done']}\n"
            f"Errors        : {STATUS_CTX['errors']}"
        )

        # ❌ SAME STATUS → SKIP EDIT
        if status_text == LAST_STATUS_TEXT:
            continue

        try:
            await bot.edit_message_text(
                chat_id,
                msg_id,
                status_text
            )
            LAST_STATUS_TEXT = status_text

        except Exception as e:
            log.warning(f"Status edit skipped: {e}")

        # ✅ COMPLETION CHECK
        if STATUS_CTX["done"] >= STATUS_CTX["total"] and STATUS_CTX["total"] != 0:
            try:
                await bot.edit_message_text(
                    chat_id,
                    msg_id,
                    "✅ Batch Completed Successfully"
                )
            except Exception:
                pass
            break

@bot.on_message(filters.command("continue"))
async def continue_handler(_, message):
    try:
        from userbot import start_b_phase, STATUS_CTX

        if STATUS_CTX["total"] == 0:
            return await message.reply("⚠️ No active batch found")

        await start_b_phase()

        await message.reply(
            "▶️ Continue triggered\n\n"
            "Processing available A-links.\n"
            "Missing A-links will be skipped."
        )

    except Exception as e:
        await message.reply(f"❌ Failed to continue\n{e}")

@bot.on_message(filters.command("get"))
async def get_json(_, message):
    if not os.path.exists("tasks.json"):
        return await message.reply("⚠️ tasks.json file does not exist")

    if os.path.getsize("tasks.json") == 0:
        return await message.reply("⚠️ tasks.json is empty")

    try:
        await message.reply_document(
            document="tasks.json",
            caption="📄 Current tasks.json"
        )
    except Exception as e:
        await message.reply(f"❌ Failed to send file\n{e}")
        
@bot.on_message(filters.command("clean"))
async def clean_json(_, message):
    try:
        with open("tasks.json", "w") as f:
            f.write("{}")

        await message.reply("🧹 tasks.json cleared successfully")
    except Exception as e:
        await message.reply(f"❌ Failed to clean file\n{e}")



@bot.on_message(filters.command("batch"))
async def batch_handler(_, message):
    global LAST_STATUS_TEXT
    LAST_STATUS_TEXT = None   # 🔥 reset for new batch

    parts = message.text.split()
    if len(parts) != 3:
        return await message.reply(
            "❌ Usage:\n/batch first_msg_link last_msg_link"
        )

    def parse(link):
        p = link.rstrip("/").split("/")
        return p[-2], int(p[-1])

    chat, first_id = parse(parts[1])
    _, last_id = parse(parts[2])
    if first_id > last_id:
        first_id, last_id = last_id, first_id

    batch_id = str(uuid.uuid4())[:8]
    log.info(f"Batch started | {batch_id}")

    status = await message.reply(
        "📦 Batch Started\n\n"
        "C links total : 0\n"
        "A links ready : 0\n"
        "Processed     : 0\n"
        "Errors        : 0"
    )

    asyncio.create_task(
        start_batch_userbot(
            chat=chat,
            first_id=first_id,
            last_id=last_id,
            batch_id=batch_id
        )
    )

    asyncio.create_task(
        status_watcher(
            message.chat.id,
            status.id
        )
    )

bot.run()