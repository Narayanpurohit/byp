import json
import re
from pyrogram import Client, filters
from config import *
from shortner import shorten_link

user = Client(
    "userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# ---------- JSON helpers ----------
def load_tasks():
    with open("tasks.json", "r") as f:
        return json.load(f)

def save_tasks(data):
    with open("tasks.json", "w") as f:
        json.dump(data, f, indent=2)

# ---------- SEND C LINKS TO X BOT ----------
async def send_c_links():
    tasks = load_tasks()
    for c_link, data in tasks.items():
        if not data["A"]:
            await user.send_message(X_BOT_USERNAME, c_link)

# ---------- X BOT REPLY HANDLER (C → A) ----------
@user.on_message(filters.chat(X_BOT_USERNAME) & filters.reply)
async def xbot_reply_handler(_, msg):
    text = msg.text or ""
    reply_text = msg.reply_to_message.text or ""

    msg_links = re.findall(r"https?://\S+", text)
    reply_links = re.findall(r"https?://\S+", reply_text)

    if not msg_links or not reply_links:
        return

    c_link = reply_links[0]
    a_link = msg_links[-1]

    tasks = load_tasks()
    if c_link in tasks and not tasks[c_link]["A"]:
        tasks[c_link]["A"] = a_link
        save_tasks(tasks)

# ---------- B BOT + SHORTENER ----------
async def process_b_links(bot):
    tasks = load_tasks()

    for c, data in list(tasks.items()):
        if not data["A"] or data["B"]:
            continue

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

                del tasks[c]
                save_tasks(tasks)
                break

# ---------- ENTRY POINT (CALLED FROM bot.py) ----------
async def start_userbot(bot):
    await user.start()
    await send_c_links()
    await process_b_links(bot)