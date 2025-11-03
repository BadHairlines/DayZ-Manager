# Back-compat: allow main.py to call utils.init_db()
async def init_db():
    """Initialize the DB pool (alias to ensure_connection)."""
    await ensure_connection()
