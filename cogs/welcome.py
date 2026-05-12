import discord
from discord.ext import commands
from datetime import datetime, timezone
import os


class WelcomeGoodbye(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Channel IDs
        self.welcome_channel_id = 1503603498850455655
        self.goodbye_channel_id = 1503603543603413134
        self.rules_channel_id = 1503604467843469444

        # Banner
        self.welcome_banner = "welcome_banner.png"

    # -----------------------------
    # HELPERS
    # -----------------------------
    async def get_channel(self, channel_id: int):
        channel = self.bot.get_channel(channel_id)
        if channel:
            return channel
        try:
            return await self.bot.fetch_channel(channel_id)
        except:
            return None

    async def send_welcome(self, member: discord.Member):
        channel = await self.get_channel(self.welcome_channel_id)
        if not channel:
            return

        embed = discord.Embed(
            title="👋 Welcome to The Hive!",
            description=(
                f"Welcome {member.mention}!\n\n"
                f"Make sure to check out <#{self.rules_channel_id}> "
                f"to get yourself **verified** and access everything.\n\n"
                f"⚡ Follow the rules, stay sharp, and enjoy your time here!"
            ),
            color=discord.Color.dark_gray(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.set_thumbnail(url=member.display_avatar.url)

        icon_url = getattr(member.guild.icon, "url", None)
        embed.set_footer(
            text=f"Member #{member.guild.member_count}",
            icon_url=icon_url
        )

        try:
            if os.path.exists(self.welcome_banner):
                file = discord.File(self.welcome_banner, filename="welcome_banner.png")
                embed.set_image(url="attachment://welcome_banner.png")

                await channel.send(
                    content=f"Welcome {member.mention} 👋",
                    embed=embed,
                    file=file
                )
            else:
                await channel.send(
                    content=f"Welcome {member.mention} 👋",
                    embed=embed
                )

        except:
            await channel.send(
                content=f"Welcome {member.mention} 👋",
                embed=embed
            )

    async def send_goodbye(self, member: discord.Member):
        channel = await self.get_channel(self.goodbye_channel_id)
        if not channel:
            return

        embed = discord.Embed(
            title="🚪 Member Left",
            description=(
                f"**{member.name}** has left the server.\n\n"
                f"We hope to see them again soon."
            ),
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Now {member.guild.member_count} members")

        await channel.send(embed=embed)

    # -----------------------------
    # EVENTS
    # -----------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self.send_welcome(member)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await self.send_goodbye(member)

    # -----------------------------
    # TEST COMMANDS
    # -----------------------------
    @commands.command()
    @commands.is_owner()
    async def test_welcome(self, ctx):
        await self.send_welcome(ctx.author)

    @commands.command()
    @commands.is_owner()
    async def test_goodbye(self, ctx):
        await self.send_goodbye(ctx.author)


async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeGoodbye(bot))
