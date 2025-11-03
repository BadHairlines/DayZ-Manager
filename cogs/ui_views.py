import discord
from discord.ext import commands
from discord.ui import View, button, Select
from cogs import utils


class FlagManageView(View):
    """Persistent interactive control panel for flag assignment and release."""

    def __init__(self, guild: discord.Guild, map_key: str, bot: commands.Bot):
        super().__init__(timeout=None)
        self.guild = guild
        self.map_key = map_key
        self.bot = bot

    # ----------------------------
    # 🔄 Internal: Refresh Display
    # ----------------------------
    async def refresh_flag_embed(self):
        guild_id = str(self.guild.id)
        try:
            embed = await utils.create_flag_embed(guild_id, self.map_key)
            async with utils.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                    guild_id,
                    self.map_key,
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

    # ----------------------------
    # 🟩 Assign Flag
    # ----------------------------
    @button(label="🟩 Assign Flag", style=discord.ButtonStyle.success)
    async def assign_flag_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("🚫 Admins only.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        guild_id = str(self.guild.id)

        # Load all unclaimed flags
        unclaimed = await utils.get_all_flags(guild_id, self.map_key)
        unclaimed = [f for f in unclaimed if f["status"] == "✅"]

        if not unclaimed:
            return await interaction.followup.send("⚠️ No unclaimed flags available.", ephemeral=True)

        flag_options = [discord.SelectOption(label=f["flag"], value=f["flag"]) for f in unclaimed]
        role_options = [
            discord.SelectOption(label=r.name, value=str(r.id))
            for r in self.guild.roles
            if not r.is_default() and not r.managed
        ]

        flag_select = Select(placeholder="Select a flag to assign", options=flag_options)
        role_select = Select(placeholder="Select a faction role", options=role_options)

        async def confirm_assign(inter2: discord.Interaction):
            flag_value = flag_select.values[0]
            role_id = role_select.values[0]
            role = self.guild.get_role(int(role_id))

            # Update flag + faction
            await utils.set_flag(guild_id, self.map_key, flag_value, "❌", str(role.id))
            async with utils.db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE factions SET claimed_flag=$1 WHERE guild_id=$2 AND role_id=$3 AND map=$4",
                    flag_value,
                    guild_id,
                    str(role.id),
                    self.map_key,
                )

            await self.refresh_flag_embed()
            await utils.log_action(
                self.guild,
                self.map_key,
                title="Flag Assigned (UI)",
                description=f"🏴 `{flag_value}` assigned to {role.mention} by {interaction.user.mention}.",
            )
            await inter2.response.edit_message(content=f"✅ Assigned `{flag_value}` to {role.mention}.", view=None)

        confirm_view = View()
        confirm_view.add_item(flag_select)
        confirm_view.add_item(role_select)
        role_select.callback = confirm_assign

        await interaction.followup.send("Select a flag and role to assign:", view=confirm_view, ephemeral=True)

    # ----------------------------
    # 🟥 Release Flag
    # ----------------------------
    @button(label="🟥 Release Flag", style=discord.ButtonStyle.danger)
    async def release_flag_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("🚫 Admins only.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        guild_id = str(self.guild.id)

        claimed = await utils.get_all_flags(guild_id, self.map_key)
        claimed = [f for f in claimed if f["status"] == "❌"]

        if not claimed:
            return await interaction.followup.send("⚠️ No claimed flags to release.", ephemeral=True)

        flag_options = [discord.SelectOption(label=f["flag"], value=f["flag"]) for f in claimed]
        flag_select = Select(placeholder="Select a flag to release", options=flag_options)

        async def confirm_release(inter2: discord.Interaction):
            flag_value = flag_select.values[0]
            await utils.release_flag(guild_id, self.map_key, flag_value)
            async with utils.db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE factions SET claimed_flag=NULL WHERE guild_id=$1 AND claimed_flag=$2 AND map=$3",
                    guild_id,
                    flag_value,
                    self.map_key,
                )

            await self.refresh_flag_embed()
            await utils.log_action(
                self.guild,
                self.map_key,
                title="Flag Released (UI)",
                description=f"🏳️ `{flag_value}` released by {interaction.user.mention}.",
            )
            await inter2.response.edit_message(content=f"✅ Released `{flag_value}`.", view=None)

        release_view = View()
        release_view.add_item(flag_select)
        flag_select.callback = confirm_release

        await interaction.followup.send("Select a flag to release:", view=release_view, ephemeral=True)
