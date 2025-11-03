import discord
from discord.ui import View, button
from cogs.utils import release_flag, log_action, MAP_DATA, create_flag_embed, db_pool


class FlagManageView(View):
    """Interactive management buttons for flag control (reassign removed)."""
    def __init__(self, guild: discord.Guild, map_key: str, flag: str, bot: discord.Bot):
        super().__init__(timeout=180)
        self.guild = guild
        self.map_key = map_key
        self.flag = flag
        self.bot = bot

    async def update_flag_display(self, guild: discord.Guild, map_key: str):
        """Refresh the live flag message."""
        guild_id = str(guild.id)
        embed = await create_flag_embed(guild_id, map_key)
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                guild_id, map_key
            )
        if not row:
            return
        channel = guild.get_channel(int(row["channel_id"]))
        try:
            msg = await channel.fetch_message(int(row["message_id"]))
            await msg.edit(embed=embed)
        except Exception:
            pass

    @button(label="🏳 Release", style=discord.ButtonStyle.secondary)
    async def release_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        guild_id = str(self.guild.id)
        await release_flag(guild_id, self.map_key, self.flag)
        await self.update_flag_display(self.guild, self.map_key)

        await log_action(
            self.guild,
            self.map_key,
            title="Flag Released (UI)",
            description=f"🏳️ {self.flag} released by {interaction.user.mention}"
        )

        await interaction.followup.send(f"✅ **{self.flag}** released successfully!", ephemeral=True)

    @button(label="❌ Close", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            await interaction.message.delete()
        except Exception:
            pass

        await interaction.followup.send("🧹 Closed flag management panel.", ephemeral=True)
