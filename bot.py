import asyncio
from pyrogram import Client, filters
from config import BOT_TOKEN, API_ID, API_HASH
from userbot import process_link, check_status

app = Client(
    "main_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@app.on_message(filters.private & filters.text)
async def main_handler(_, message):
    text = message.text.strip()

    # /check command
    if text == "/check":
        await message.reply("🔍 Status check ho raha hai, wait karo...")
        asyncio.create_task(check_status(message.from_user.id))
        return

    # link handler
    await message.reply("✅ Link received, processing start...")
    asyncio.create_task(process_link(text))

app.run()