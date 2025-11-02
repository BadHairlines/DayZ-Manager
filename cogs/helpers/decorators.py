# cogs/helpers/decorators.py
import discord
from discord import app_commands
from functools import wraps

# ✅ Shared map dropdown for all commands
MAP_CHOICES = [
    app_commands.Choice(name="Livonia", value="livonia"),
    app_commands.Choice(name="Chernarus", value="chernarus"),
    app_commands.Choice(name="Sakhal", value="sakhal"),
]

def normalize_map(map_choice: app_commands.Choice[str] | str) -> str:
    """Ensure map keys are lowercase and safe for DB use."""
    if isinstance(map_choice, app_commands.Choice):
        return map_choice.value.lower()
    return str(map_choice).lower()

# ✅ Admin-only decorator for both slash & prefix commands
def admin_only():
    def decorator(func):
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "🚫 You must be an **administrator** to use this command.",
                    ephemeral=True
                )
                return
            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator
