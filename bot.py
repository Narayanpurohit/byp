import asyncio
import logging
import uuid
from pyrogram import Client, filters
from config import *
from userbot import start_batch_userbot

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

@bot.on_message(filters.command("batch"))
async def batch_handler(_, message):
    try:
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
                status_chat=message.chat.id,
                status_msg=status.id,
                batch_id=batch_id
            )
        )

    except Exception:
        log.exception("Batch handler failed")
        await message.reply("❌ Internal error")

bot.run()