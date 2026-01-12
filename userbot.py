import re
import asyncio
import time
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, RPCError
from logger import get_logger
from config import (
    API_ID, API_HASH, SESSION_STRING,
    X_BOT_USERNAME, Y_GROUP_ID, BOT_TOKEN,
    STATUS_TIMEOUT
)

log = get_logger("USERBOT")

userbot = Client(
    "userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

PENDING_CHECK = {}

# ---------- LINK PROCESS ----------
async def process_link(link):
    try:
        await userbot.send_message(X_BOT_USERNAME, link)
        log.info("Link sent to X bot")

    except FloodWait as e:
        log.warning(f"FloodWait process_link {e.value}s")
        await asyncio.sleep(e.value)

    except RPCError as e:
        log.error(f"RPC error: {e}")

    except Exception:
        log.exception("process_link failed")

# ---------- X BOT REPLY ----------
@userbot.on_message(filters.chat(X_BOT_USERNAME))
async def xbot_reply(_, message):
    try:
        if not message.text:
            return

        match = re.search(r"https?://mega\.nz/\S+", message.text)
        if not match:
            return

        mega_link = match.group()

        await userbot.send_message(
            Y_GROUP_ID,
            f"/l2 {mega_link}"
        )

        log.info("Mega link sent to Y group (/l2 format)")

    except FloodWait as e:
        await asyncio.sleep(e.value)

    except Exception:
        log.exception("xbot_reply error")

# ---------- /check ----------
async def check_status(user_id):
    try:
        PENDING_CHECK[user_id] = time.time()
        await userbot.send_message(Y_GROUP_ID, "/status2")
        log.info(f"/status2 sent for user {user_id}")

    except Exception:
        log.exception("check_status failed")

# ---------- STATUS REPLY ----------
@userbot.on_message(filters.chat(Y_GROUP_ID))
async def status_reply(_, message):
    try:
        if not message.from_user or not message.from_user.is_bot:
            return

        now = time.time()

        expired = [
            uid for uid, t in PENDING_CHECK.items()
            if now - t > STATUS_TIMEOUT
        ]
        for uid in expired:
            PENDING_CHECK.pop(uid, None)

        if not PENDING_CHECK:
            return

        user_id = next(iter(PENDING_CHECK))
        PENDING_CHECK.pop(user_id, None)

        async with Client(
            "callback_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN
        ) as bot:
            await bot.send_message(
                user_id,
                f"📊 Status Result:\n\n{message.text}"
            )

        log.info(f"Status reply sent to user {user_id}")

    except FloodWait as e:
        await asyncio.sleep(e.value)

    except Exception:
        log.exception("status_reply error")

# ---------- START USERBOT ----------
try:
    log.info("Userbot started")
    userbot.start()
except Exception as e:
    log.critical(f"Userbot crashed: {e}")