import discord
from discord import app_commands
from discord.ext import commands

class BanNotification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="ban",
        description="Send a DayZ ban notification."
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        gamertag="The player's gamertag",
        user="The Discord user",
        reason="Reason for the ban",
        duration="Ban duration",
        bail="Bail amount",
        channel="Channel to send the notification to"
    )
    async def ban(
        self,
        interaction: discord.Interaction,
        gamertag: str,
        user: discord.Member,
        reason: str,
        duration: str,
        bail: str,
        channel: discord.TextChannel
    ):

        # Confirmation to the admin
        confirm = discord.Embed(
            description=(
                f"> **Banned:** `{gamertag}`\n"
                f"> **Reason:** `{reason}`\n"
                f"> **Duration:** `{duration}`\n"
                f"> **Bail Amount:** `{bail}`\n"
                f"> **Message Sent To:** {channel.mention}"
            ),
            color=discord.Color.random()
        )
        confirm.set_footer(
            text="DayZ Manager",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )

        await interaction.response.send_message(embed=confirm, ephemeral=True)

        # Public Ban Embed
        embed = discord.Embed(
            title="🔨 Ban Notification 🔨",
            color=discord.Color.random()
        )

        embed.description = (
            f"__**GAMERTAG:**__ `{gamertag}`\n\n"
            f"__**DISCORD:**__ {user.mention}\n"
            f"__**USER ID:**__ `{user.id}`\n\n"
            f"__**REASON:**__ [{reason}](https://discord.com/channels/1109306235808911360/1109306236903633001)\n"
            f"__**DURATION:**__ `{duration}`\n"
            f"__**BAIL AMOUNT:**__ `{bail}`\n\n"
            f"__**Paying Bail:**__\n"
            f"*To pay your bail, make a ticket in "
            f"https://discord.com/channels/1109306235808911360/1109306236903633003 "
            f'under the option **"Pay Bail"**.*\n\n'
            f"__**Ban Appeals:**__\n"
            f"*To appeal your ban, make a ticket in "
            f"https://discord.com/channels/1109306235808911360/1109306236903633003 "
            f'under the option **"Support"**.*'
        )

        embed.set_image(
            url="https://i.makeagif.com/media/12-20-2014/Lo3Taj.gif"
        )

        embed.set_footer(
            text="DayZ Manager",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )

        await channel.send(embed=embed)

    @ban.error
    async def ban_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ This command is for admins only.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(BanNotification(bot))
