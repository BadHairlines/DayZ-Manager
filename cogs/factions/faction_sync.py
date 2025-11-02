import discord
from discord import app_commands
from discord.ext import commands
from cogs.helpers.base_cog import BaseCog
from cogs.helpers.decorators import admin_only
from cogs.utils import sync_faction_claims, db_pool
import asyncio


class FactionSync(commands.Cog, BaseCog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="sync-factions",
        description="🔁 Sync all existing factions with current flag ownership data."
    )
    @admin_only()
    async def sync_factions(self, interaction: discord.Interaction):
        """Admin-only command to realign faction.claimed_flag with flags table."""
        await interaction.response.defer(thinking=True, ephemeral=True)
        guild = interaction.guild
        guild_id = str(guild.id)

        if not db_pool:
            await interaction.followup.send("❌ Database not initialized. Please try again later.", ephemeral=True)
            return

        try:
            await sync_faction_claims(guild_id)
            await asyncio.sleep(1)

            embed = self.make_embed(
                "__FACTION SYNC COMPLETE__",
                (
                    f"✅ All factions in **{guild.name}** have been synced with current flag ownership.\n\n"
                    f"🧩 Any missing or mismatched `claimed_flag` values have been updated automatically.\n"
                    f"⚙️ This helps align the database after map resets or manual flag assignments."
                ),
                0x2ECC71,
                "🔁",
                "Faction Sync"
            )
            embed.set_footer(text="Faction ↔ Flag Data Sync", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
            embed.timestamp = discord.utils.utcnow()

            await interaction.followup.send(embed=embed, ephemeral=True)
            print(f"✅ Synced faction claims for {guild.name} ({guild_id})")

        except Exception as e:
            await interaction.followup.send(f"❌ Sync failed:\n```{e}```", ephemeral=True)
            print(f"❌ Faction sync failed for {guild.name}: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(FactionSync(bot))
