# Back-compat: allow main.py to call utils.init_db()
from cogs.utils import ensure_connection


async def init_db():
    """Initialize the DB pool (alias to ensure_connection)."""
    await ensure_connection()
