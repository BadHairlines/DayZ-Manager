import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random
from datetime import datetime

from cogs.utils import log_action


class ActivityCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.required_reactions = 4
        self.expiry_hours = 12
        self.emoji = "✅"

    def make_embed(self, name: str, role: discord.Role | None, color: int):
        """Creates an embed for the activity check."""
        mention_text = role.mention if role else f"**{name}**"
        embed = discord.Embed(
            title="__**ACTIVITY CHECK**__",
            description=f"> At least **{self.required_reactions}** members of {mention_text} must click {self.emoji} below!",
            color=color
        )
        embed.add_field(name="Progress", value=f"✅ 0/{self.required_reactions} confirmed", inline=False)
        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        embed.timestamp = discord.utils.utcnow()
        return embed

    @app_commands.command(name="activity-check", description="Run activity checks for all faction channels in a category (map).")
    @app_commands.describe(category="Select the category that contains all faction channels.")
    async def activity_check(self, interaction: discord.Interaction, category: discord.CategoryChannel):
        """Posts activity checks in every text channel inside the selected category."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admins only!", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)
        color = random.randint(0, 0xFFFFFF)
        sent_count = 0

        for channel in category.text_channels:
            try:
                # Try to match a faction role name to the channel name
                matched_role = discord.utils.find(
                    lambda r: r.name.lower().replace(" ", "-") in channel.name.lower(),
                    interaction.guild.roles
                )

                embed = self.make_embed(channel.name, matched_role, color)
                content = matched_role.mention if matched_role else None
                msg = await channel.send(content=content, embed=embed)
                await msg.add_reaction(self.emoji)
                sent_count += 1
                await asyncio.sleep(1)

            except discord.Forbidden:
                print(f"⚠️ No permission to send messages in {channel.name}.")
            except Exception as e:
                print(f"⚠️ Failed to post in {channel.name}: {e}")

        await interaction.followup.send(
            f"✅ Sent activity checks to **{sent_count}** channels in **{category.name}**!",
            ephemeral=True
        )

        # Log the operation
        await log_action(
            interaction.guild,
            category.name,
            title="Category Activity Check Started",
            description=f"📢 {interaction.user.mention} launched activity checks in **{category.name}**.",
            color=0x00BFFF
        )


async def setup(bot):
    await bot.add_cog(ActivityCheck(bot))
