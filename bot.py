import asyncio
import json
import re
from pyrogram import Client, filters
from config import *
from userbot import start_userbot

bot = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ---------- JSON helpers ----------
def load_tasks():
    try:
        with open("tasks.json", "r") as f:
            return json.load(f)
    except:
        return {}

def save_tasks(data):
    with open("tasks.json", "w") as f:
        json.dump(data, f, indent=2)

# ---------- STATUS UPDATER ----------
async def status_updater(msg):
    while True:
        tasks = load_tasks()
        total = len(tasks)
        done = sum(1 for x in tasks.values() if x.get("short"))

        await msg.edit(
            f"""
📊 **Batch Status**

Total Links : `{total}`
Completed  : `{done}`
Pending    : `{total-done}`

⏳ Auto update every 5 sec
"""
        )

        if total and total == done:
            await msg.edit("✅ **Batch Completed Successfully**")
            break

        await asyncio.sleep(5)

# ---------- /batch COMMAND ----------
@bot.on_message(filters.command("batch"))
async def batch_handler(_, msg):
    try:
        _, first, last = msg.text.split()
        first = int(first.split("/")[-1])
        last = int(last.split("/")[-1])
    except:
        return await msg.reply("❌ Use:\n/batch first_msg_link last_msg_link")

    status = await msg.reply("🚀 **Process Started...**")
    tasks = load_tasks()

    async for m in bot.get_chat_history(msg.chat.id, offset_id=first - 1):
        if m.id > last:
            continue

        text = (m.text or "").replace(REPLACE_FROM, REPLACE_TO)
        sent = await bot.send_message(Y_CHAT_ID, text)

        for link in re.findall(r"https?://\S+", text):
            if C_DOMAIN in link:
                tasks[link] = {
                    "msg_id": sent.id,
                    "A": "",
                    "B": "",
                    "short": ""
                }

        if m.id == last:
            break

    save_tasks(tasks)

    asyncio.create_task(status_updater(status))
    asyncio.create_task(start_userbot(bot))

bot.run()