import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random
from datetime import datetime, timedelta

from cogs.utils import log_action, get_all_flags, release_flag, db_pool


class ActivityCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.required_reactions = 4
        self.expiry_hours = 12
        self.emoji = "✅"

    def make_embed(self, role: discord.Role, color, progress=0, complete=False, failed=False):
        """Builds the embed for the check."""
        desc = f"> At least **{self.required_reactions}** members of {role.mention} must click {self.emoji} below!"

        if complete:
            desc = f"✅ **Activity Check Complete!** {role.mention} met the requirement!"
        elif failed:
            desc = f"❌ **Activity Check Failed!** Not enough members of {role.mention} responded."

        embed = discord.Embed(title="__**ACTIVITY CHECK**__", description=desc, color=color)
        if not complete and not failed:
            embed.add_field(name="Progress", value=f"✅ {progress}/{self.required_reactions} confirmed", inline=False)

        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        embed.timestamp = discord.utils.utcnow()
        return embed

    @app_commands.command(name="activity-check", description="Run activity checks for all factions in a category (map).")
    @app_commands.describe(
        category="The category containing all faction channels for this map."
    )
    async def activity_check(self, interaction: discord.Interaction, category: discord.CategoryChannel):
        """Posts activity checks in every faction channel inside the selected category."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admins only!", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)
        color = random.randint(0, 0xFFFFFF)
        guild = interaction.guild
        guild_id = str(guild.id)
        sent_count = 0

        # Iterate through each channel inside the category
        for channel in category.text_channels:
            try:
                # Try to match a faction role name to the channel name
                matched_role = discord.utils.find(
                    lambda r: r.name.lower().replace(" ", "-") in channel.name.lower(),
                    guild.roles
                )
                if not matched_role:
                    continue

                # Create and send the embed
                embed = self.make_embed(matched_role, color)
                msg = await channel.send(content=matched_role.mention, embed=embed)
                await msg.add_reaction(self.emoji)
                sent_count += 1
                await asyncio.sleep(1)

            except Exception as e:
                print(f"⚠️ Failed to post in {channel.name}: {e}")

        await interaction.followup.send(
            f"✅ Sent activity checks to **{sent_count}** faction channels in **{category.name}**!",
            ephemeral=True
        )

        # 🪵 Log the launch of category-wide checks
        await log_action(
            guild,
            category.name,
            title="Category Activity Check Started",
            description=f"📢 {interaction.user.mention} launched activity checks for **{category.name}**.",
            color=0x00BFFF
        )


async def setup(bot):
    await bot.add_cog(ActivityCheck(bot))
