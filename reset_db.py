import asyncio
import os
from cogs.utils import init_db, db_pool

# 🔹 Optional: manually set DATABASE_URL if Railway doesn’t auto-load it
# os.environ["DATABASE_URL"] = "postgresql://postgres:YOUR_PASSWORD@postgres.railway.internal:5432/railway"

async def reset_database():
    print("🔄 Initializing database connection...")
    await init_db()
    if not db_pool:
        raise RuntimeError("❌ Database pool not initialized. Check DATABASE_URL env variable.")

    async with db_pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE flags;")
        print("✅ Flags table has been fully wiped clean.")

asyncio.run(reset_database())
