import discord
from discord import app_commands
from discord.ext import commands
import random

class ActivityCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def make_embed(self, role, color):
        embed = discord.Embed(
            title="__**ACTIVITY CHECK**__",
            description=f"""
> At least **FOUR** members of {role.mention} must click the ✅ below this message!
            """,
            color=color
        )
        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        embed.timestamp = discord.utils.utcnow()
        return embed

    @app_commands.command(name="activity-check", description="Start an activity check for a faction or role.")
    @app_commands.describe(role="Select the faction or role to ping for activity")
    async def activity_check(self, interaction: discord.Interaction, role: discord.Role):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ This command is for admins ONLY!", ephemeral=True)
            return

        color = random.randint(0, 0xFFFFFF)
        embed = self.make_embed(role, color)

        # Send the message and add reaction
        msg = await interaction.channel.send(content=role.mention, embed=embed)
        await msg.add_reaction("✅")

        await interaction.response.send_message(f"✅ Activity check started for {role.mention}!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ActivityCheck(bot))
