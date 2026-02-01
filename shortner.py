import aiohttp
from config import SHORTNER_DOMAIN, SHORTNER_API

async def shorten_link(url: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(
            SHORTNER_DOMAIN,
            params={
                "api": SHORTNER_API,
                "url": url
            },
            timeout=15
        ) as resp:
            data = await resp.json()

            if data.get("status") != "success":
                raise ValueError("Shortener failed")

            return data["shortenedUrl"]