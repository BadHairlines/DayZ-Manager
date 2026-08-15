import discord

from discord import app_commands
from functools import wraps
from typing import Union, Callable, Awaitable, TypeVar, ParamSpec

from cogs import utils


# =========================================================
# TYPE SAFETY
# =========================================================

P = ParamSpec("P")
T = TypeVar("T")


# =========================================================
# MAP CHOICES
# =========================================================

MAP_CHOICES = [
    app_commands.Choice(
        name="Livonia",
        value="livonia",
    ),
    app_commands.Choice(
        name="Chernarus",
        value="chernarus",
    ),
    app_commands.Choice(
        name="Sakhal",
        value="sakhal",
    ),
]


def normalize_map(
    map_choice: Union[
        app_commands.Choice[str],
        str
    ]
) -> str:

    if isinstance(
        map_choice,
        app_commands.Choice
    ):
        return utils.normalize_map(
            map_choice.value
        )

    return utils.normalize_map(
        str(map_choice)
    )


# =========================================================
# ADMIN CHECK
# =========================================================

def admin_only():

    def decorator(
        func: Callable[
            P,
            Awaitable[T]
        ]
    ):

        @wraps(func)
        async def wrapper(
            self,
            interaction: discord.Interaction,
            *args: P.args,
            **kwargs: P.kwargs,
        ):

            # -------------------------------------------------
            # SERVER ONLY
            # -------------------------------------------------

            if interaction.guild is None:

                if interaction.response.is_done():
                    return

                return await interaction.response.send_message(
                    "⚠️ This command can only be used inside a server.",
                    ephemeral=True,
                )

            # -------------------------------------------------
            # ADMIN ONLY
            # -------------------------------------------------

            if not interaction.user.guild_permissions.administrator:

                try:

                    if interaction.response.is_done():

                        await interaction.followup.send(
                            "🚫 Administrator permissions required.",
                            ephemeral=True,
                        )

                    else:

                        await interaction.response.send_message(
                            "🚫 Administrator permissions required.",
                            ephemeral=True,
                        )

                except (
                    discord.InteractionResponded,
                    discord.NotFound,
                    discord.HTTPException,
                ):
                    pass

                return

            return await func(
                self,
                interaction,
                *args,
                **kwargs,
            )

        return wrapper

    return decorator
