import asyncio
import hashlib
import logging

import discord
from discord.ext import commands
from discord.ui import View, Select

from cogs import utils


log = logging.getLogger("dayz-manager")

MAX_SELECT_OPTIONS = 25


# =========================================================
# ASSIGN BUTTON
# =========================================================

class AssignFlagButton(discord.ui.Button):

    def __init__(
        self,
        custom_id: str,
    ):

        super().__init__(
            label="🟩 Assign Flag",
            style=discord.ButtonStyle.success,
            custom_id=custom_id,
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ):

        view = self.view

        if isinstance(
            view,
            FlagManageView
        ):
            await view.assign_flag(
                interaction
            )


# =========================================================
# RELEASE BUTTON
# =========================================================

class ReleaseFlagButton(discord.ui.Button):

    def __init__(
        self,
        custom_id: str,
    ):

        super().__init__(
            label="🟥 Release Flag",
            style=discord.ButtonStyle.danger,
            custom_id=custom_id,
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ):

        view = self.view

        if isinstance(
            view,
            FlagManageView
        ):
            await view.release_flag(
                interaction
            )


# =========================================================
# FLAG MANAGEMENT VIEW
# =========================================================

class FlagManageView(
    View
):

    _locks: dict[str, asyncio.Lock] = {}

    def __init__(
        self,
        guild: discord.Guild | None,
        map_key: str,
        server: str,
        bot: commands.Bot,
    ):

        # IMPORTANT:
        # Persistent Discord views MUST have timeout=None.
        super().__init__(
            timeout=None
        )

        self.guild = guild
        self.bot = bot

        self.map_key = utils.normalize_map(
            map_key
        )

        self.server = utils.normalize_server(
            server
        )

        guild_key = (
            str(guild.id)
            if guild
            else "global"
        )

        raw_key = (
            f"{guild_key}:"
            f"{self.map_key}:"
            f"{self.server}"
        )

        identifier = hashlib.sha1(
            raw_key.encode("utf-8")
        ).hexdigest()[:16]

        self.add_item(
            AssignFlagButton(
                f"flag_assign:{identifier}"
            )
        )

        self.add_item(
            ReleaseFlagButton(
                f"flag_release:{identifier}"
            )
        )

    # =========================================================
    # SESSION KEY
    # =========================================================

    @property
    def session_key(
        self
    ) -> str:

        guild_id = (
            self.guild.id
            if self.guild
            else "global"
        )

        return (
            f"{guild_id}:"
            f"{self.map_key}:"
            f"{self.server}"
        )

    def get_lock(
        self
    ) -> asyncio.Lock:

        if self.session_key not in self._locks:

            self._locks[
                self.session_key
            ] = asyncio.Lock()

        return self._locks[
            self.session_key
        ]

    # =========================================================
    # REFRESH PUBLIC EMBED
    # =========================================================

    async def refresh_flag_embed(
        self
    ):

        if not self.guild:
            return

        try:

            await utils.refresh_flag_embed(
                self.bot,
                str(self.guild.id),
                self.map_key,
                self.server,
            )

            # Re-register this exact persistent view
            # on the message after refresh.
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
                    self.server,
                )

            if not row:
                return

            channel = self.guild.get_channel(
                int(row["channel_id"])
            )

            if not channel:
                return

            message = await channel.fetch_message(
                int(row["message_id"])
            )

            await message.edit(
                view=self
            )

        except (
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException,
        ):
            return

        except Exception:

            log.exception(
                "Failed to refresh flag embed."
            )

    # =========================================================
    # ROLE OPTIONS
    # =========================================================

    async def role_options(
        self
    ):

        if not self.guild:
            return []

        roles = [
            role
            for role in self.guild.roles
            if not role.is_default()
            and not role.managed
        ]

        roles.sort(
            key=lambda role: (
                -role.position,
                role.name.lower(),
            )
        )

        return [
            discord.SelectOption(
                label=role.name[:100],
                value=str(role.id),
            )
            for role in roles[
                :MAX_SELECT_OPTIONS
            ]
        ]

    # =========================================================
    # CANCEL
    # =========================================================

    async def cancel(
        self,
        interaction: discord.Interaction,
    ):

        try:

            await interaction.response.edit_message(
                content="❌ Cancelled.",
                view=None,
            )

        except (
            discord.NotFound,
            discord.HTTPException,
        ):
            pass

    # =========================================================
    # ASSIGN
    # =========================================================

    async def assign_flag(
        self,
        interaction: discord.Interaction,
    ):

        if not interaction.user.guild_permissions.administrator:

            return await interaction.response.send_message(
                "🚫 Admins only.",
                ephemeral=True,
            )

        lock = self.get_lock()

        if lock.locked():

            return await interaction.response.send_message(
                "⚠️ Another flag action is currently in progress.",
                ephemeral=True,
            )

        async with lock:

            await interaction.response.defer(
                ephemeral=True
            )

            if not self.guild:
                return

            guild_id = str(
                self.guild.id
            )

            flags = await utils.get_all_flags(
                guild_id,
                self.map_key,
                self.server,
            )

            available = [
                row
                for row in flags
                if row["status"] == "✅"
                and not row["role_id"]
            ]

            if not available:

                return await interaction.followup.send(
                    "⚠️ No unclaimed flags.",
                    ephemeral=True,
                )

            options = [
                discord.SelectOption(
                    label=f"🟩 {row['flag']}",
                    value=row["flag"],
                )
                for row in available[
                    :MAX_SELECT_OPTIONS
                ]
            ]

            select = Select(
                placeholder="Select a flag",
                options=options,
            )

            view = View(
                timeout=60
            )

            view.add_item(
                select
            )

            cancel_button = discord.ui.Button(
                label="Cancel",
                style=discord.ButtonStyle.secondary,
            )

            async def cancel_callback(
                inter: discord.Interaction
            ):

                await inter.response.edit_message(
                    content="❌ Cancelled.",
                    view=None,
                )

            cancel_button.callback = (
                cancel_callback
            )

            view.add_item(
                cancel_button
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
                    flag,
                )

                if (
                    not row
                    or row["status"] != "✅"
                    or row["role_id"]
                ):

                    return await inter.followup.edit_message(
                        message_id=inter.message.id,
                        content=(
                            "⚠️ That flag is no longer "
                            "available."
                        ),
                        view=None,
                    )

                roles = await self.role_options()

                if not roles:

                    return await inter.followup.edit_message(
                        message_id=inter.message.id,
                        content=(
                            "⚠️ No assignable roles "
                            "were found."
                        ),
                        view=None,
                    )

                role_select = Select(
                    placeholder="Select a role",
                    options=roles,
                )

                role_view = View(
                    timeout=60
                )

                role_view.add_item(
                    role_select
                )

                async def on_role(
                    inter2: discord.Interaction
                ):

                    await inter2.response.defer(
                        ephemeral=True
                    )

                    role_id = int(
                        role_select.values[0]
                    )

                    role = self.guild.get_role(
                        role_id
                    )

                    if not role:

                        return await inter2.followup.edit_message(
                            message_id=inter2.message.id,
                            content="⚠️ Role not found.",
                            view=None,
                        )

                    # Re-check the flag immediately
                    # before assigning.
                    current = await utils.get_flag(
                        guild_id,
                        self.map_key,
                        self.server,
                        flag,
                    )

                    if (
                        not current
                        or current["status"] != "✅"
                        or current["role_id"]
                    ):

                        return await inter2.followup.edit_message(
                            message_id=inter2.message.id,
                            content=(
                                "⚠️ That flag was already "
                                "claimed by someone else."
                            ),
                            view=None,
                        )

                    await utils.set_flag(
                        guild_id,
                        self.map_key,
                        self.server,
                        flag,
                        "❌",
                        str(role.id),
                    )

                    await self.refresh_flag_embed()

                    await inter2.followup.edit_message(
                        message_id=inter2.message.id,
                        content=(
                            f"🏴 **{flag} → {role.mention}** assigned.\n"
                            f"🗺️ Map: **{self.map_key.title()}**\n"
                            f"🖥️ Server: **{self.server}**"
                        ),
                        view=None,
                    )

                role_select.callback = on_role

                await inter.followup.edit_message(
                    message_id=inter.message.id,
                    content=(
                        f"Select a role for **{flag}**\n"
                        f"🗺️ Map: **{self.map_key.title()}**\n"
                        f"🖥️ Server: **{self.server}**"
                    ),
                    view=role_view,
                )

            select.callback = on_select

            await interaction.followup.send(
                (
                    f"Choose a flag:\n"
                    f"🗺️ Map: **{self.map_key.title()}**\n"
                    f"🖥️ Server: **{self.server}**"
                ),
                view=view,
                ephemeral=True,
            )

    # =========================================================
    # RELEASE
    # =========================================================

    async def release_flag(
        self,
        interaction: discord.Interaction,
    ):

        if not interaction.user.guild_permissions.administrator:

            return await interaction.response.send_message(
                "🚫 Admins only.",
                ephemeral=True,
            )

        lock = self.get_lock()

        if lock.locked():

            return await interaction.response.send_message(
                "⚠️ Another flag action is currently in progress.",
                ephemeral=True,
            )

        async with lock:

            await interaction.response.defer(
                ephemeral=True
            )

            if not self.guild:
                return

            guild_id = str(
                self.guild.id
            )

            flags = await utils.get_all_flags(
                guild_id,
                self.map_key,
                self.server,
            )

            claimed = [
                row
                for row in flags
                if row["status"] == "❌"
                and row["role_id"]
            ]

            if not claimed:

                return await interaction.followup.send(
                    "⚠️ No claimed flags.",
                    ephemeral=True,
                )

            options = [
                discord.SelectOption(
                    label=f"🟥 {row['flag']}",
                    value=row["flag"],
                )
                for row in claimed[
                    :MAX_SELECT_OPTIONS
                ]
            ]

            select = Select(
                placeholder="Select flag",
                options=options,
            )

            view = View(
                timeout=60
            )

            view.add_item(
                select
            )

            cancel_button = discord.ui.Button(
                label="Cancel",
                style=discord.ButtonStyle.secondary,
            )

            async def cancel_callback(
                inter: discord.Interaction
            ):

                await inter.response.edit_message(
                    content="❌ Cancelled.",
                    view=None,
                )

            cancel_button.callback = (
                cancel_callback
            )

            view.add_item(
                cancel_button
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
                    flag,
                )

                if (
                    not row
                    or row["status"] != "❌"
                    or not row["role_id"]
                ):

                    return await inter.followup.edit_message(
                        message_id=inter.message.id,
                        content=(
                            "⚠️ That flag is already "
                            "unclaimed."
                        ),
                        view=None,
                    )

                await utils.release_flag(
                    guild_id,
                    self.map_key,
                    self.server,
                    flag,
                )

                await self.refresh_flag_embed()

                await inter.followup.edit_message(
                    message_id=inter.message.id,
                    content=(
                        f"🏳️ **{flag} released**\n"
                        f"🗺️ Map: **{self.map_key.title()}**\n"
                        f"🖥️ Server: **{self.server}**"
                    ),
                    view=None,
                )

            select.callback = on_select

            await interaction.followup.send(
                (
                    f"Choose a flag:\n"
                    f"🗺️ Map: **{self.map_key.title()}**\n"
                    f"🖥️ Server: **{self.server}**"
                ),
                view=view,
                ephemeral=True,
            )
