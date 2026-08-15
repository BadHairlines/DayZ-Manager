import asyncio
import hashlib
import logging

import discord

from discord.ext import commands
from discord.ui import View, Select

from cogs import utils


log = logging.getLogger("dayz-manager")

MAX_SELECT_OPTIONS = 25


class FlagManageView(View):

    _locks: dict[str, asyncio.Lock] = {}

    def __init__(
        self,
        guild: discord.Guild | None,
        map_key: str,
        server: str,
        bot: commands.Bot
    ):

        super().__init__(timeout=None)

        self.guild = guild
        self.map_key = map_key
        self.server = utils.normalize_server(server)
        self.bot = bot

        # -----------------------------------------
        # UNIQUE CUSTOM IDS
        # -----------------------------------------
        raw_key = (
            f"{guild.id if guild else 'global'}:"
            f"{map_key}:"
            f"{self.server}"
        )

        identifier = hashlib.sha1(
            raw_key.encode("utf-8")
        ).hexdigest()[:16]

        # Give each server its own button IDs
        for item in self.children:

            if isinstance(
                item,
                discord.ui.Button
            ):

                if item.label == "🟩 Assign Flag":
                    item.custom_id = (
                        f"assign_flag:{identifier}"
                    )

                elif item.label == "🟥 Release Flag":
                    item.custom_id = (
                        f"release_flag:{identifier}"
                    )

    # -----------------------------
    # LOCKING
    # -----------------------------
    @property
    def session_key(self) -> str:

        return (
            f"{self.guild.id if self.guild else 'global'}:"
            f"{self.map_key}:"
            f"{self.server}"
        )

    def get_lock(self) -> asyncio.Lock:

        if self.session_key not in self._locks:
            self._locks[self.session_key] = asyncio.Lock()

        return self._locks[self.session_key]

    # -----------------------------
    # EMBED REFRESH
    # -----------------------------
    async def refresh_flag_embed(self):

        try:

            if not self.guild:
                return

            embed = await utils.create_flag_embed(
                str(self.guild.id),
                self.map_key,
                self.server
            )

            async with utils.safe_acquire() as conn:

                row = await conn.fetchrow(
                    """
                    SELECT channel_id, message_id
                    FROM flag_messages
                    WHERE guild_id=$1
                      AND map=$2
                      AND server=$3
                    """,
                    str(self.guild.id),
                    self.map_key,
                    self.server
                )

            if not row:
                return

            channel = self.guild.get_channel(
                int(row["channel_id"])
            )

            if not channel:
                return

            try:

                msg = await channel.fetch_message(
                    int(row["message_id"])
                )

                await msg.edit(
                    embed=embed,
                    view=self
                )

            except (
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException
            ):
                return

        except Exception as e:

            log.warning(
                f"Failed embed refresh: {e}"
            )

    # -----------------------------
    # ROLE OPTIONS
    # -----------------------------
    async def role_options(self):

        roles = [
            r
            for r in self.guild.roles
            if not r.is_default()
            and not r.managed
        ]

        roles.sort(
            key=lambda r: (
                -r.position,
                r.name.lower()
            )
        )

        return [
            discord.SelectOption(
                label=r.name[:100],
                value=str(r.id)
            )
            for r in roles[:MAX_SELECT_OPTIONS]
        ]

    # -----------------------------
    # CANCEL
    # -----------------------------
    async def cancel(
        self,
        interaction: discord.Interaction
    ):

        await interaction.response.edit_message(
            content="❌ Cancelled.",
            view=None
        )

    # =========================================================
    # ASSIGN
    # =========================================================
    async def assign_flag(
        self,
        interaction: discord.Interaction
    ):

        if not interaction.user.guild_permissions.administrator:

            return await interaction.response.send_message(
                "🚫 Admins only.",
                ephemeral=True
            )

        lock = self.get_lock()

        if lock.locked():

            return await interaction.response.send_message(
                "⚠️ Another action is in progress. Please wait.",
                ephemeral=True
            )

        async with lock:

            await interaction.response.defer(
                ephemeral=True
            )

            guild_id = str(
                self.guild.id
            )

            flags = await utils.get_all_flags(
                guild_id,
                self.map_key,
                self.server
            )

            available = [
                f
                for f in flags
                if f["status"] == "✅"
            ]

            if not available:

                return await interaction.followup.send(
                    "⚠️ No unclaimed flags.",
                    ephemeral=True
                )

            options = [
                discord.SelectOption(
                    label=f"🟩 {f['flag']}",
                    value=f["flag"]
                )
                for f in available[:MAX_SELECT_OPTIONS]
            ]

            select = Select(
                placeholder="Select a flag",
                options=options
            )

            view = View(
                timeout=60
            )

            view.add_item(select)

            cancel_btn = discord.ui.Button(
                label="Cancel",
                style=discord.ButtonStyle.secondary
            )

            cancel_btn.callback = self.cancel

            view.add_item(
                cancel_btn
            )

            async def on_select(
                inter: discord.Interaction
            ):

                await inter.response.defer(
                    ephemeral=True
                )

                flag = select.values[0]

                row = await utils.get_flag(
                    guild_id,
                    self.map_key,
                    self.server,
                    flag
                )

                if not row or row["status"] != "✅":

                    return await inter.followup.edit_message(
                        message_id=inter.message.id,
                        content="⚠️ Flag no longer available.",
                        view=None
                    )

                roles = await self.role_options()

                if not roles:

                    return await inter.followup.edit_message(
                        message_id=inter.message.id,
                        content="⚠️ No roles available.",
                        view=None
                    )

                role_select = Select(
                    placeholder="Assign role",
                    options=roles
                )

                step = View(
                    timeout=60
                )

                step.add_item(
                    role_select
                )

                async def on_role(
                    inter2: discord.Interaction
                ):

                    await inter2.response.defer(
                        ephemeral=True
                    )

                    role = self.guild.get_role(
                        int(role_select.values[0])
                    )

                    if not role:

                        return await inter2.followup.edit_message(
                            message_id=inter.message.id,
                            content="⚠️ Role not found.",
                            view=None
                        )

                    await utils.set_flag(
                        guild_id,
                        self.map_key,
                        self.server,
                        flag,
                        "❌",
                        str(role.id)
                    )

                    await self.refresh_flag_embed()

                    await inter2.followup.edit_message(
                        message_id=inter.message.id,
                        content=(
                            f"🏴 **{flag} → {role.mention}** assigned.\n"
                            f"🖥️ Server: **{self.server}**"
                        ),
                        view=None
                    )

                role_select.callback = on_role

                await inter.followup.edit_message(
                    message_id=inter.message.id,
                    content=(
                        f"Select role for **{flag}**\n"
                        f"🖥️ Server: **{self.server}**"
                    ),
                    view=step
                )

            select.callback = on_select

            await interaction.followup.send(
                "Choose a flag:",
                view=view,
                ephemeral=True
            )

    # =========================================================
    # RELEASE
    # =========================================================
    async def release_flag(
        self,
        interaction: discord.Interaction
    ):

        if not interaction.user.guild_permissions.administrator:

            return await interaction.response.send_message(
                "🚫 Admins only.",
                ephemeral=True
            )

        lock = self.get_lock()

        if lock.locked():

            return await interaction.response.send_message(
                "⚠️ Another action is in progress. Please wait.",
                ephemeral=True
            )

        async with lock:

            await interaction.response.defer(
                ephemeral=True
            )

            guild_id = str(
                self.guild.id
            )

            flags = await utils.get_all_flags(
                guild_id,
                self.map_key,
                self.server
            )

            claimed = [
                f
                for f in flags
                if f["status"] == "❌"
            ]

            if not claimed:

                return await interaction.followup.send(
                    "⚠️ No claimed flags.",
                    ephemeral=True
                )

            options = [
                discord.SelectOption(
                    label=f"🟥 {f['flag']}",
                    value=f["flag"]
                )
                for f in claimed[:MAX_SELECT_OPTIONS]
            ]

            select = Select(
                placeholder="Select flag",
                options=options
            )

            view = View(
                timeout=60
            )

            view.add_item(
                select
            )

            cancel_btn = discord.ui.Button(
                label="Cancel",
                style=discord.ButtonStyle.secondary
            )

            cancel_btn.callback = self.cancel

            view.add_item(
                cancel_btn
            )

            async def on_select(
                inter: discord.Interaction
            ):

                await inter.response.defer(
                    ephemeral=True
                )

                flag = select.values[0]

                row = await utils.get_flag(
                    guild_id,
                    self.map_key,
                    self.server,
                    flag
                )

                if not row or row["status"] != "❌":

                    return await inter.followup.edit_message(
                        message_id=inter.message.id,
                        content="⚠️ Already unclaimed.",
                        view=None
                    )

                await utils.release_flag(
                    guild_id,
                    self.map_key,
                    self.server,
                    flag
                )

                await self.refresh_flag_embed()

                await inter.followup.edit_message(
                    message_id=inter.message.id,
                    content=(
                        f"🏳️ **{flag} released**\n"
                        f"🖥️ Server: **{self.server}**"
                    ),
                    view=None
                )

            select.callback = on_select

            await interaction.followup.send(
                "Choose a flag:",
                view=view,
                ephemeral=True
            )


# =========================================================
# PERSISTENT BUTTONS
# =========================================================

class AssignFlagButton(
    discord.ui.Button
):

    def __init__(
        self,
        custom_id: str
    ):

        super().__init__(
            label="🟩 Assign Flag",
            style=discord.ButtonStyle.success,
            custom_id=custom_id
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        view = self.view

        if isinstance(
            view,
            FlagManageView
        ):
            await view.assign_flag(
                interaction
            )


class ReleaseFlagButton(
    discord.ui.Button
):

    def __init__(
        self,
        custom_id: str
    ):

        super().__init__(
            label="🟥 Release Flag",
            style=discord.ButtonStyle.danger,
            custom_id=custom_id
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        view = self.view

        if isinstance(
            view,
            FlagManageView
        ):
            await view.release_flag(
                interaction
            )
