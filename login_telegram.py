import asyncio
from pyrogram import Client
import config

async def main():
    client = Client(
        config.SESSION_FILE,
        api_id=config.API_ID,
        api_hash=config.API_HASH
    )
    await client.start()
    print("Logged in successfully!")
    await client.stop()

if __name__ == "__main__":
    asyncio.run(main())