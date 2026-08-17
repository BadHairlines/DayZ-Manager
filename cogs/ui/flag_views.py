from __future__ import annotations

import asyncio
import hashlib
import logging

import discord
from discord.ext import commands

from cogs import utils

log = logging.getLogger("dayz-manager")
MAX_SELECT_OPTIONS = 25


class FlagManageView(discord.ui.View):
    _locks: dict[str, asyncio.Lock] = {}

    def __init__(
        self,
        guild: discord.Guild | None,
        map_key: str,
        server: str,
        bot: commands.Bot,
    ):
        super().__init__(timeout=None)

        self.guild = guild
        self.bot = bot
        self.map_key = utils.normalize_map(map_key)
        self.server = utils.normalize_server(server)

        guild_key = str(guild.id) if guild else "global"
        raw = f"{guild_key}:{self.map_key}:{self.server}"
        identifier = hashlib.sha1(raw.encode()).hexdigest()[:16]

        self.add_item(AssignFlagButton(f"flag_assign:{identifier}"))
        self.add_item(ReleaseFlagButton(f"flag_release:{identifier}"))

    @property
    def session_key(self) -> str:
        return f"{self.guild.id if self.guild else 'global'}:{self.map_key}:{self.server}"

    def get_lock(self) -> asyncio.Lock:
        lock = self._locks.get(self.session_key)
        if lock is None:
            lock = self._locks[self.session_key] = asyncio.Lock()
        return lock

    async def refresh_message(self) -> None:
        if not self.guild:
            return

        row = await utils.get_flag_message(
            str(self.guild.id), self.map_key, self.server
        )
        if not row:
            return

        channel = self.guild.get_channel(int(row["channel_id"]))
        if not isinstance(channel, discord.TextChannel):
            return

        try:
            message = await channel.fetch_message(int(row["message_id"]))
            embed = await utils.create_flag_embed(
                str(self.guild.id), self.map_key, self.server, self.guild
            )
            await message.edit(embed=embed, view=self)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return

    async def role_options(self) -> list[discord.SelectOption]:
        if not self.guild:
            return []

        roles = [
            role
            for role in self.guild.roles
            if not role.is_default()
            and not role.managed
            and role.name.startswith("Faction-")
        ]

        roles.sort(key=lambda r: (-r.position, r.name.casefold()))

        return [
            discord.SelectOption(label=role.name[:100], value=str(role.id))
            for role in roles[:MAX_SELECT_OPTIONS]
        ]

    async def assign_flag(self, interaction: discord.Interaction) -> None:
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "🚫 Administrator permissions required.", ephemeral=True
            )

        lock = self.get_lock()
        if lock.locked():
            return await interaction.response.send_message(
                "⚠️ Another flag action is currently in progress.", ephemeral=True
            )

        if not self.guild:
            return

        async with lock:
            await interaction.response.defer(ephemeral=True)

            flags = await utils.get_all_flags(
                str(self.guild.id), self.map_key, self.server
            )
            available = [
                row for row in flags
                if row["status"] == "✅" and row["role_id"] is None
            ]

            if not available:
                return await interaction.followup.send(
                    "⚠️ No unclaimed flags are available.", ephemeral=True
                )

            flag_options = [
                discord.SelectOption(
                    label=f"🟩 {row['flag']}",
                    value=row["flag"],
                )
                for row in available[:MAX_SELECT_OPTIONS]
            ]

            flag_select = discord.ui.Select(
                placeholder="Select a flag",
                options=flag_options,
                min_values=1,
                max_values=1,
            )

            view = discord.ui.View(timeout=60)
            view.add_item(flag_select)

            cancel = discord.ui.Button(
                label="Cancel",
                style=discord.ButtonStyle.secondary,
            )

            async def cancel_cb(inter: discord.Interaction):
                await inter.response.edit_message(
                    content="❌ Cancelled.", view=None
                )

            cancel.callback = cancel_cb
            view.add_item(cancel)

            async def flag_cb(inter: discord.Interaction):
                flag = flag_select.values[0]
                roles = await self.role_options()

                if not roles:
                    return await inter.response.edit_message(
                        content="⚠️ No assignable `Faction-` roles were found.",
                        view=None,
                    )

                role_select = discord.ui.Select(
                    placeholder=f"Select a role for {flag}",
                    options=roles,
                )
                role_view = discord.ui.View(timeout=60)
                role_view.add_item(role_select)

                async def role_cb(inter2: discord.Interaction):
                    role_id = int(role_select.values[0])
                    role = self.guild.get_role(role_id)

                    if not role:
                        return await inter2.response.edit_message(
                            content="⚠️ Role not found.", view=None
                        )

                    result = await utils.claim_flag(
                        str(self.guild.id),
                        self.map_key,
                        self.server,
                        flag,
                        str(role.id),
                    )

                    if not result:
                        return await inter2.response.edit_message(
                            content="⚠️ That flag was already claimed or is no longer available.",
                            view=None,
                        )

                    await self.refresh_message()

                    await inter2.response.edit_message(
                        content=(
                            f"🏴 **{flag} → {role.mention}** assigned.\n"
                            f"🗺️ Map: **{self.map_key.title()}**\n"
                            f"🖥️ Server: **{self.server}**"
                        ),
                        view=None,
                    )

                role_select.callback = role_cb

                await inter.response.edit_message(
                    content=(
                        f"Choose a role for **{flag}**.\n"
                        f"🗺️ Map: **{self.map_key.title()}**\n"
                        f"🖥️ Server: **{self.server}**"
                    ),
                    view=role_view,
                )

            flag_select.callback = flag_cb

            await interaction.followup.send(
                (
                    f"Choose a flag.\n"
                    f"🗺️ Map: **{self.map_key.title()}**\n"
                    f"🖥️ Server: **{self.server}**"
                ),
                view=view,
                ephemeral=True,
            )

    async def release_flag(self, interaction: discord.Interaction) -> None:
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "🚫 Administrator permissions required.", ephemeral=True
            )

        lock = self.get_lock()
        if lock.locked():
            return await interaction.response.send_message(
                "⚠️ Another flag action is currently in progress.", ephemeral=True
            )

        if not self.guild:
            return

        async with lock:
            await interaction.response.defer(ephemeral=True)

            flags = await utils.get_all_flags(
                str(self.guild.id), self.map_key, self.server
            )
            claimed = [
                row for row in flags
                if row["status"] == "❌" and row["role_id"]
            ]

            if not claimed:
                return await interaction.followup.send(
                    "⚠️ No claimed flags.", ephemeral=True
                )

            options = [
                discord.SelectOption(
                    label=f"🟥 {row['flag']}",
                    value=row["flag"],
                )
                for row in claimed[:MAX_SELECT_OPTIONS]
            ]

            select = discord.ui.Select(
                placeholder="Select a claimed flag",
                options=options,
            )
            view = discord.ui.View(timeout=60)
            view.add_item(select)

            async def callback(inter: discord.Interaction):
                flag = select.values[0]

                result = await utils.release_flag(
                    str(self.guild.id),
                    self.map_key,
                    self.server,
                    flag,
                )

                if not result:
                    return await inter.response.edit_message(
                        content="⚠️ That flag is already unclaimed.",
                        view=None,
                    )

                await self.refresh_message()

                await inter.response.edit_message(
                    content=(
                        f"🏳️ **{flag} released.**\n"
                        f"🗺️ Map: **{self.map_key.title()}**\n"
                        f"🖥️ Server: **{self.server}**"
                    ),
                    view=None,
                )

            select.callback = callback

            await interaction.followup.send(
                (
                    f"Choose a flag to release.\n"
                    f"🗺️ Map: **{self.map_key.title()}**\n"
                    f"🖥️ Server: **{self.server}**"
                ),
                view=view,
                ephemeral=True,
            )


class AssignFlagButton(discord.ui.Button):
    def __init__(self, custom_id: str):
        super().__init__(
            label="Assign Flag",
            emoji="🟩",
            style=discord.ButtonStyle.success,
            custom_id=custom_id,
        )

    async def callback(self, interaction: discord.Interaction):
        if isinstance(self.view, FlagManageView):
            await self.view.assign_flag(interaction)


class ReleaseFlagButton(discord.ui.Button):
    def __init__(self, custom_id: str):
        super().__init__(
            label="Release Flag",
            emoji="🟥",
            style=discord.ButtonStyle.danger,
            custom_id=custom_id,
        )

    async def callback(self, interaction: discord.Interaction):
        if isinstance(self.view, FlagManageView):
            await self.view.release_flag(interaction)
