import re
import asyncio
from pyrogram import Client, filters
from config import (
    API_ID, API_HASH, SESSION_STRING,
    X_BOT_USERNAME, Y_GROUP_ID, BOT_TOKEN
)

# store pending /check user
PENDING_CHECK = {}

userbot = Client(
    "userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# -------- LINK FLOW --------

async def process_link(link):
    async with userbot:
        await userbot.send_message(X_BOT_USERNAME, link)

@userbot.on_message(filters.chat(X_BOT_USERNAME))
async def xbot_reply(_, message):
    if not message.text:
        return

    # extract mega.nz link
    match = re.search(r"https?://mega\.nz/\S+", message.text)
    if match:
        mega_link = match.group()
        await userbot.send_message(Y_GROUP_ID, mega_link)

# -------- /check FLOW --------

async def check_status(user_id):
    async with userbot:
        PENDING_CHECK["user"] = user_id
        await userbot.send_message(Y_GROUP_ID, "/status2")

@userbot.on_message(filters.chat(Y_GROUP_ID))
async def status_reply(_, message):
    if "user" not in PENDING_CHECK:
        return

    # sirf bot reply accept
    if message.from_user and message.from_user.is_bot:
        user_id = PENDING_CHECK.pop("user")

        async with Client(
            "send_back_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN
        ) as bot:
            await bot.send_message(
                user_id,
                f"📊 Status Reply:\n\n{message.text}"
            )

userbot.start()