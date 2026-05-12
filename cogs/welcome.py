import discord
from discord.ext import commands


class WelcomeGoodbye(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # OPTIONAL: hardcode or move to env vars
        self.welcome_channel_id = 1503603498850455655
        self.goodbye_channel_id = 1503603543603413134

    # -----------------------------
    # MEMBER JOIN (WELCOME)
    # -----------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        channel = self.bot.get_channel(self.welcome_channel_id)

        if channel is None:
            return

        embed = discord.Embed(
            title="👋 Welcome!",
            description=f"Welcome to **{member.guild.name}**, {member.mention}!",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Member #{member.guild.member_count}")

        await channel.send(embed=embed)

    # -----------------------------
    # MEMBER LEAVE (GOODBYE)
    # -----------------------------
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        channel = self.bot.get_channel(self.goodbye_channel_id)

        if channel is None:
            return

        embed = discord.Embed(
            title="👋 Goodbye!",
            description=f"{member.name} left the server.",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Now {member.guild.member_count} members")

        await channel.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeGoodbye(bot))
