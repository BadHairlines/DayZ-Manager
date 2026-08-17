from __future__ import annotations

from typing import Union

import discord
from discord import app_commands

from cogs import utils

MAP_CHOICES = [
    app_commands.Choice(name="Livonia", value="livonia"),
    app_commands.Choice(name="Chernarus", value="chernarus"),
    app_commands.Choice(name="Sakhal", value="sakhal"),
]


def normalize_map(
    map_choice: Union[app_commands.Choice[str], str]
) -> str:
    if isinstance(map_choice, app_commands.Choice):
        return utils.normalize_map(map_choice.value)
    return utils.normalize_map(str(map_choice))


def admin_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            raise app_commands.CheckFailure(
                "This command can only be used inside a server."
            )

        if not interaction.user.guild_permissions.administrator:
            raise app_commands.CheckFailure(
                "Administrator permissions required."
            )

        return True

    return app_commands.check(predicate)
