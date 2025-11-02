import discord
from discord.ui import View, button, Select
from cogs.utils import release_flag, set_flag, log_action, get_all_flags, create_flag_embed, db_pool

class RoleSelect(discord.ui.Select):
    def __init__(self, guild, map_key, flag, parent_view):
        self.guild, self.map_key, self.flag, self.parent_view = guild, map_key, flag, parent_view
        options = [discord.SelectOption(label=r.name, value=str(r.id)) for r in guild.roles if not r.is_default() and not r.is_bot_managed() and r.name != "@everyone"][:25]
        super().__init__(placeholder="Select a new faction/role...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Admins only.", ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        guild_id = str(self.guild.id)
        new_role = self.guild.get_role(int(self.values[0]))
        existing_flags = await get_all_flags(guild_id, self.map_key)
        for record in existing_flags:
            if record["role_id"] == str(new_role.id):
                await interaction.followup.send(f"{new_role.mention} already owns **{record['flag']}** on this map.", ephemeral=True); return
        await set_flag(guild_id, self.map_key, self.flag, "❌", str(new_role.id))
        await self.parent_view.update_flag_display(self.guild, self.map_key)
        await log_action(self.guild, self.map_key, title="Flag Reassigned (UI)", description=f"{self.flag} → {new_role.mention} (by {interaction.user.mention})")
        await interaction.followup.send(f"Flag {self.flag} reassigned to {new_role.mention}.", ephemeral=True)
        self.parent_view.stop()

class FlagManageView(View):
    def __init__(self, guild:discord.Guild, map_key:str, flag:str, bot:discord.Bot):
        super().__init__(timeout=180)
        self.guild, self.map_key, self.flag, self.bot = guild, map_key, flag, bot

    async def update_flag_display(self, guild:discord.Guild, map_key:str):
        guild_id = str(guild.id)
        embed = await create_flag_embed(guild_id, map_key)
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT channel_id,message_id FROM flag_messages WHERE guild_id=$1 AND map=$2", guild_id, map_key)
        if not row: return
        channel = guild.get_channel(int(row["channel_id"]))
        try:
            msg = await channel.fetch_message(int(row["message_id"]))
            await msg.edit(embed=embed)
        except Exception: return

    @button(label="Reassign", style=discord.ButtonStyle.primary)
    async def reassign_button(self, interaction:discord.Interaction, button:discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Admins only.", ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        view = View(timeout=60); view.add_item(RoleSelect(self.guild, self.map_key, self.flag, self))
        await interaction.followup.send("Select a new role for this flag:", view=view, ephemeral=True)

    @button(label="Release", style=discord.ButtonStyle.secondary)
    async def release_button(self, interaction:discord.Interaction, button:discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Admins only.", ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        guild_id = str(self.guild.id)
        await release_flag(guild_id, self.map_key, self.flag)
        await self.update_flag_display(self.guild, self.map_key)
        await log_action(self.guild, self.map_key, title="Flag Released (UI)", description=f"{self.flag} released by {interaction.user.mention}")
        await interaction.followup.send(f"Flag {self.flag} released successfully.", ephemeral=True)

    @button(label="Close", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction:discord.Interaction, button:discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Admins only.", ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        try: await interaction.message.delete()
        except Exception: pass
        await interaction.followup.send("Closed flag management panel.", ephemeral=True)
