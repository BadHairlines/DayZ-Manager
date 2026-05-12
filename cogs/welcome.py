import discord
from discord.ext import commands
from datetime import datetime


class WelcomeGoodbye(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Set these in your main file or env later
        self.welcome_channel_id = None
        self.goodbye_channel_id = None

        # Optional: rules channel id (like your screenshot)
        self.rules_channel_id = None

        # Optional banner image (local file or hosted URL)
        self.welcome_banner = "welcome_banner.png"

    # -----------------------------
    # MEMBER JOIN (WELCOME)
    # -----------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        channel = self.bot.get_channel(self.welcome_channel_id)
        if channel is None:
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
            timestamp=datetime.utcnow()
        )

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(
            text=f"Member #{member.guild.member_count}",
            icon_url=member.guild.icon.url if member.guild.icon else None
        )

        # Add banner image (like your screenshot style)
        try:
            file = discord.File(self.welcome_banner, filename="welcome_banner.png")
            embed.set_image(url="attachment://welcome_banner.png")

            await channel.send(
                content=f"Welcome {member.mention} 👋",
                embed=embed,
                file=file
            )
        except:
            # fallback if image missing
            await channel.send(
                content=f"Welcome {member.mention} 👋",
                embed=embed
            )

    # -----------------------------
    # MEMBER LEAVE (GOODBYE)
    # -----------------------------
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        channel = self.bot.get_channel(self.goodbye_channel_id)
        if channel is None:
            return

        embed = discord.Embed(
            title="🚪 Member Left",
            description=(
                f"**{member.name}** has left the server.\n\n"
                f"We hope to see them again soon."
            ),
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Now {member.guild.member_count} members")

        await channel.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeGoodbye(bot))
