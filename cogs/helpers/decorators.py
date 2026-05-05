import discord
from discord import app_commands
from functools import wraps
from typing import Union, Callable, Awaitable, TypeVar, ParamSpec


# -----------------------------
# TYPE SAFETY
# -----------------------------
P = ParamSpec("P")
T = TypeVar("T")


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

    def decorator(func: Callable[P, Awaitable[T]]):

        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args: P.args, **kwargs: P.kwargs):

            # -----------------------------
            # FIX: safer guild check
            # -----------------------------
            if interaction.guild is None or interaction.user is None:
                if interaction.response.is_done():
                    return
                return await interaction.response.send_message(
                    "⚠️ Server only command.",
                    ephemeral=True
                )

            # -----------------------------
            # FIX: defer-safe response handling
            # -----------------------------
            if not interaction.user.guild_permissions.administrator:
                try:
                    if interaction.response.is_done():
                        await interaction.followup.send(
                            "🚫 Administrator permissions required.",
                            ephemeral=True
                        )
                    else:
                        await interaction.response.send_message(
                            "🚫 Administrator permissions required.",
                            ephemeral=True
                        )
                except discord.InteractionResponded:
                    pass
                return

            return await func(self, interaction, *args, **kwargs)

        return wrapper

    return decorator
