import discord
from discord import app_commands
from functools import wraps
from typing import Union

MAP_CHOICES = [
    app_commands.Choice(name="Livonia", value="livonia"),
    app_commands.Choice(name="Chernarus", value="chernarus"),
    app_commands.Choice(name="Sakhal", value="sakhal"),
]

def normalize_map(map_choice: Union[app_commands.Choice[str], str]) -> str:
    """Return a lowercase map key for DB use."""
    return (map_choice.value if isinstance(map_choice, app_commands.Choice) else str(map_choice)).lower()

def admin_only():
    """Decorator to restrict a command to guild administrators."""
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
