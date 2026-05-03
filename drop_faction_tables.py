import os
import asyncio
import asyncpg


TABLES_TO_DROP = [
    "action_logs",
    "faction_logs",
    "factions"
]


async def main():
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL missing")

    if dsn.startswith("postgres://"):
        dsn = dsn.replace("postgres://", "postgresql://", 1)

    conn = await asyncpg.connect(dsn)

    try:
        for table in TABLES_TO_DROP:
            print(f"Dropping {table}...")
            await conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")

        print("✅ All faction tables removed successfully.")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
