import discord
from discord import app_commands
from functools import wraps
from typing import Union, Callable, Awaitable


# ---------------- MAPS ----------------

MAP_CHOICES = [
    app_commands.Choice(name="Livonia", value="livonia"),
    app_commands.Choice(name="Chernarus", value="chernarus"),
    app_commands.Choice(name="Sakhal", value="sakhal"),
]


def normalize_map(map_choice: Union[app_commands.Choice[str], str]) -> str:
    """
    Convert map input into a consistent DB-safe lowercase key.
    """
    return (
        map_choice.value
        if isinstance(map_choice, app_commands.Choice)
        else str(map_choice)
    ).lower()


# ---------------- PERMISSIONS ----------------

def admin_only() -> Callable:
    """
    Restrict slash commands to server administrators only.
    """

    def decorator(func: Callable[..., Awaitable]):
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):

            # Must be in a server
            if not interaction.guild:
                await interaction.response.send_message(
                    "⚠️ This command can only be used in a server.",
                    ephemeral=True
                )
                return

            # Must be admin
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "🚫 Administrator permissions required.",
                    ephemeral=True
                )
                return

            return await func(self, interaction, *args, **kwargs)

        return wrapper

    return decorator
