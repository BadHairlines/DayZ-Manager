import discord
from discord import app_commands
from functools import wraps
from typing import Union, Callable, Awaitable


# -----------------------------
# MAP CONFIG
# -----------------------------
MAP_CHOICES = [
    app_commands.Choice(name="Livonia", value="livonia"),
    app_commands.Choice(name="Chernarus", value="chernarus"),
    app_commands.Choice(name="Sakhal", value="sakhal"),
]


def normalize_map(map_choice: Union[app_commands.Choice[str], str]) -> str:
    """Normalize map input into DB-safe lowercase key."""
    if isinstance(map_choice, app_commands.Choice):
        return map_choice.value.lower()
    return str(map_choice).lower()


# -----------------------------
# PERMISSION DECORATOR
# -----------------------------
def admin_only():
    """
    Restrict slash commands to server administrators only.
    """

    def decorator(func: Callable[..., Awaitable]):

        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):

            if not interaction.guild:
                return await interaction.response.send_message(
                    "⚠️ Server only command.",
                    ephemeral=True
                )

            if not interaction.user.guild_permissions.administrator:
                return await interaction.response.send_message(
                    "🚫 Administrator permissions required.",
                    ephemeral=True
                )

            return await func(self, interaction, *args, **kwargs)

        return wrapper

    return decorator
