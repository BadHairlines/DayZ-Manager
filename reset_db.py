import asyncio
import os
from cogs import utils

async def reset_database():
    print("🔄 Initializing database connection...")
    await utils.init_db()

    # Wait for db_pool to initialize
    if not utils.db_pool:
        print("⚠️ Retrying connection...")
        await asyncio.sleep(1)
        if not utils.db_pool:
            raise RuntimeError("❌ Database pool not initialized. Check DATABASE_URL env variable.")

    async with utils.db_pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE flags;")
        print("✅ Flags table has been fully wiped clean.")

asyncio.run(reset_database())
