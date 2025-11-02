import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from cogs.utils import db_pool
from .faction_utils import ensure_faction_table, make_embed

MAP_CHOICES = [...]
COLOR_CHOICES = [...]

class FactionCreate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="create-faction", description="Create a faction with a role, channel, and members.")
    @app_commands.choices(map=MAP_CHOICES, color=COLOR_CHOICES)
    async def create_faction(self, interaction, name: str, map, color, leader: discord.Member, member1=None, member2=None, member3=None):
        await interaction.response.defer(thinking=True)
        await ensure_faction_table()

        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("❌ Admin only.", ephemeral=True)

        guild = interaction.guild
        role_color = discord.Color(int(color.value.strip("#"), 16))
        async with db_pool.acquire() as conn:
            existing = await conn.fetchrow("SELECT * FROM factions WHERE guild_id=$1 AND faction_name ILIKE $2", str(guild.id), name)
        if existing:
            return await interaction.followup.send(f"⚠️ Faction `{name}` already exists!", ephemeral=True)

        # create role, channel, assign members, store in DB...
        # (reuse your logic exactly as-is)

async def setup(bot):
    await bot.add_cog(FactionCreate(bot))
