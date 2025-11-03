import discord
from discord.ext import commands
from discord.ui import View, button, Select
from cogs import utils

MAX_SELECT_OPTIONS = 25  # Discord limit


class FlagManageView(View):
    """Persistent control panel for flag assignment and release."""
    # Lock per guild+map to prevent overlap
    active_sessions: dict[str, bool] = {}

    def __init__(self, guild: discord.Guild, map_key: str, bot: commands.Bot):
        super().__init__(timeout=None)
        self.guild = guild
        self.map_key = map_key
        self.bot = bot

    # --- session helpers ---
    @property
    def _session_key(self) -> str:
        return f"{self.guild.id}:{self.map_key}"

    def _is_busy(self) -> bool:
        return self.active_sessions.get(self._session_key, False)

    def _lock(self) -> None:
        self.active_sessions[self._session_key] = True

    def _unlock(self) -> None:
        self.active_sessions.pop(self._session_key, None)

    # --- display refresh ---
    async def refresh_flag_embed(self):
        guild_id = str(self.guild.id)
        try:
            embed = await utils.create_flag_embed(guild_id, self.map_key)
            async with utils.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                    guild_id, self.map_key,
                )
            if not row:
                return
            channel = self.guild.get_channel(int(row["channel_id"]))
            if not channel:
                return
            msg = await channel.fetch_message(int(row["message_id"]))
            await msg.edit(embed=embed, view=self)
        except Exception as e:
            print(f"⚠️ Failed to refresh flag embed: {e}")

    # --- helpers ---
    def _role_options(self) -> list[discord.SelectOption]:
        roles = [r for r in self.guild.roles if not r.is_default() and not r.managed]
        roles.sort(key=lambda r: (-r.position, r.name.lower()))
        return [
            discord.SelectOption(label=r.name[:100], value=str(r.id))
            for r in roles[:MAX_SELECT_OPTIONS]
        ]

    # --- assign flag ---
    @button(label="🟩 Assign Flag", style=discord.ButtonStyle.success, custom_id="assign_flag_btn")
    async def assign_flag_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("🚫 Admins only.", ephemeral=True)

        if self._is_busy():
            return await interaction.response.send_message(
                "⚠️ Another admin is currently assigning or releasing a flag for this map in this guild. Please wait.",
                ephemeral=True
            )
        self._lock()

        try:
            await interaction.response.defer(ephemeral=True)

            guild_id = str(self.guild.id)
            all_flags = await utils.get_all_flags(guild_id, self.map_key)
            unclaimed = [f for f in all_flags if f["status"] == "✅"]
            if not unclaimed:
                return await interaction.followup.send("⚠️ No unclaimed flags available.", ephemeral=True)

            flag_options = [
                discord.SelectOption(label=f"🟩 {f['flag']}", value=f["flag"])
                for f in unclaimed[:MAX_SELECT_OPTIONS]
            ]
            flag_select = Select(placeholder="🏴 Select a flag to assign", options=flag_options)
            cancel_button = discord.ui.Button(label="❌ Cancel", style=discord.ButtonStyle.secondary)

            step1_view = View()
            step1_view.add_item(flag_select)
            step1_view.add_item(cancel_button)

            async def cancel_action(inter_cancel: discord.Interaction):
                self._unlock()
                await inter_cancel.response.edit_message(content="❌ Assignment cancelled.", view=None)
            cancel_button.callback = cancel_action

            async def flag_chosen(inter2: discord.Interaction):
                await inter2.response.defer(ephemeral=True)
                selected_flag = flag_select.values[0]

                row_now = await utils.get_flag(guild_id, self.map_key, selected_flag)
                if not row_now or row_now["status"] != "✅":
                    self._unlock()
                    return await inter2.followup.edit_message(
                        message_id=inter2.message.id,
                        content=f"⚠️ Flag `{selected_flag}` is no longer available.",
                        view=None
                    )

                role_opts = self._role_options()
                if not role_opts:
                    self._unlock()
                    return await inter2.followup.edit_message(
                        message_id=inter2.message.id,
                        content="⚠️ No eligible roles found to assign.",
                        view=None
                    )

                role_select = Select(
                    placeholder=f"🎭 Assign `{selected_flag}` to...",
                    options=role_opts,
                    min_values=1,
                    max_values=1,
                )
                step2_view = View()
                step2_view.add_item(role_select)
                step2_view.add_item(cancel_button)

                async def role_chosen(inter3: discord.Interaction):
                    await inter3.response.defer(ephemeral=True)
                    try:
                        role_id = int(role_select.values[0])
                        role = self.guild.get_role(role_id)
                        if not role:
                            return await inter3.followup.edit_message(
                                message_id=inter2.message.id,
                                content="⚠️ That role no longer exists.",
                                view=None
                            )

                        row_now2 = await utils.get_flag(guild_id, self.map_key, selected_flag)
                        if not row_now2 or row_now2["status"] != "✅":
                            return await inter3.followup.edit_message(
                                message_id=inter2.message.id,
                                content=f"⚠️ Flag `{selected_flag}` was just claimed by someone else.",
                                view=None
                            )

                        await utils.set_flag(guild_id, self.map_key, selected_flag, "❌", str(role.id))
                        async with utils.db_pool.acquire() as conn:
                            await conn.execute(
                                "UPDATE factions SET claimed_flag=$1 WHERE guild_id=$2 AND role_id=$3 AND map=$4",
                                selected_flag, guild_id, str(role.id), self.map_key
                            )

                        await self.refresh_flag_embed()
                        await utils.log_action(
                            self.guild, self.map_key,
                            title="Flag Assigned (UI)",
                            description=f"🏴 `{selected_flag}` assigned to {role.mention} by {interaction.user.mention}.",
                        )

                        embed = discord.Embed(
                            title="✅ Flag Assigned",
                            description=f"🏴 **{selected_flag}** → {role.mention}\n🗺️ *{self.map_key.title()}*",
                            color=0x2ECC71
                        )
                        await inter3.followup.edit_message(message_id=inter2.message.id, embed=embed, view=None)

                        # Do not react to ephemeral messages
                    finally:
                        self._unlock()

                role_select.callback = role_chosen
                await inter2.followup.edit_message(
                    message_id=inter2.message.id,
                    content=f"🏴 Flag `{selected_flag}` selected. Now choose a role to assign it to:",
                    view=step2_view
                )

            flag_select.callback = flag_chosen
            await interaction.followup.send("Select a flag to assign:", view=step1_view, ephemeral=True)

        except Exception:
            self._unlock()
            raise

    # --- release flag ---
    @button(label="🟥 Release Flag", style=discord.ButtonStyle.danger, custom_id="release_flag_btn")
    async def release_flag_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("🚫 Admins only.", ephemeral=True)

        if self._is_busy():
            return await interaction.response.send_message(
                "⚠️ Another admin is currently assigning or releasing a flag for this map in this guild. Please wait.",
                ephemeral=True
            )
        self._lock()

        try:
            await interaction.response.defer(ephemeral=True)

            guild_id = str(self.guild.id)
            all_flags = await utils.get_all_flags(guild_id, self.map_key)
            claimed = [f for f in all_flags if f["status"] == "❌"]
            if not claimed:
                return await interaction.followup.send("⚠️ No claimed flags to release.", ephemeral=True)

            flag_options = [
                discord.SelectOption(label=f"🟥 {f['flag']}", value=f["flag"])
                for f in claimed[:MAX_SELECT_OPTIONS]
            ]
            flag_select = Select(placeholder="🏳️ Select a flag to release", options=flag_options)
            cancel_button = discord.ui.Button(label="❌ Cancel", style=discord.ButtonStyle.secondary)

            step_view = View()
            step_view.add_item(flag_select)
            step_view.add_item(cancel_button)

            async def cancel_action(inter_cancel: discord.Interaction):
                self._unlock()
                await inter_cancel.response.edit_message(content="❌ Release cancelled.", view=None)
            cancel_button.callback = cancel_action

            async def flag_chosen(inter2: discord.Interaction):
                await inter2.response.defer(ephemeral=True)
                flag_value = flag_select.values[0]

                try:
                    row_now = await utils.get_flag(guild_id, self.map_key, flag_value)
                    if not row_now or row_now["status"] != "❌":
                        return await inter2.followup.edit_message(
                            message_id=inter2.message.id,
                            content=f"⚠️ `{flag_value}` is already unclaimed.",
                            view=None
                        )

                    await utils.release_flag(guild_id, self.map_key, flag_value)
                    async with utils.db_pool.acquire() as conn:
                        await conn.execute(
                            "UPDATE factions SET claimed_flag=NULL WHERE guild_id=$1 AND claimed_flag=$2 AND map=$3",
                            guild_id, flag_value, self.map_key
                        )

                    await self.refresh_flag_embed()
                    await utils.log_action(
                        self.guild, self.map_key,
                        title="Flag Released (UI)",
                        description=f"🏳️ `{flag_value}` released by {interaction.user.mention}.",
                    )

                    embed = discord.Embed(
                        title="✅ Flag Released",
                        description=f"🏳️ **{flag_value}** has been made available again.\n🗺️ *{self.map_key.title()}*",
                        color=0x95A5A6
                    )
                    await inter2.followup.edit_message(message_id=inter2.message.id, embed=embed, view=None)

                    # Do not react to ephemeral messages
                finally:
                    self._unlock()

            flag_select.callback = flag_chosen
            await interaction.followup.send("Select a flag to release:", view=step_view, ephemeral=True)

        except Exception:
            self._unlock()
            raise
