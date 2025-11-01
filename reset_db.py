import asyncio
from cogs.utils import init_db, db_pool

async def reset_database():
    await init_db()
    async with db_pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE flags;")
        print("✅ Flags table has been fully wiped clean.")

asyncio.run(reset_database())
