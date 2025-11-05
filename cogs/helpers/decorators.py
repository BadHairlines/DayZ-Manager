# cogs/helpers/decorators.py
import discord
from discord import app_commands
from functools import wraps
from typing import Union, Callable, Awaitable

# --- Static map options for setup/commands ---
MAP_CHOICES = [
    app_commands.Choice(name="Livonia", value="livonia"),
    app_commands.Choice(name="Chernarus", value="chernarus"),
    app_commands.Choice(name="Sakhal", value="sakhal"),
]


def normalize_map(map_choice: Union[app_commands.Choice[str], str]) -> str:
    """
    Normalize a map name (from a string or Choice) into a lowercase DB-safe key.
    Example: Choice(name='Livonia', value='livonia') -> 'livonia'
    """
    return (map_choice.value if isinstance(map_choice, app_commands.Choice) else str(map_choice)).lower()


def admin_only() -> Callable:
    """
    Decorator for slash commands to restrict use to guild administrators.
    Sends an ephemeral error message if permission is denied or in DMs.
    """
    def decorator(func: Callable[..., Awaitable]):
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            if not interaction.guild:
                await interaction.response.send_message(
                    "⚠️ This command can only be used **within a server**.",
                    ephemeral=True
                )
                return

            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "🚫 You must be an **administrator** to use this command.",
                    ephemeral=True
                )
                return

            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator
