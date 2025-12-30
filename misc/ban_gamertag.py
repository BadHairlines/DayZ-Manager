import discord
from discord import app_commands
from discord.ext import commands
import random

STAFF_ROLE_ID = 1109306236110909567  # ✅ your staff role

def staff_only():
    async def predicate(interaction: discord.Interaction):
        # Allow admins automatically
        if interaction.user.guild_permissions.administrator:
            return True

        # Check for staff role
        return any(role.id == STAFF_ROLE_ID for role in interaction.user.roles)

    return app_commands.check(predicate)


class GamertagBan(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="ban_gamertag",
        description="Send a gamertag ban notification embed"
    )
    @staff_only()  # ✅ staff role OR admin
    @app_commands.describe(
        gamertag="Banned gamertag",
        user="Linked Discord user (optional)",
        reason="Reason for the ban",
        duration="Ban duration",
        bail="Bail amount",
        channel="Channel to send the ban notice"
    )
    async def ban_gamertag(
        self,
        interaction: discord.Interaction,
        gamertag: str,
        user: discord.User | None,  # ✅ optional
        reason: str,
        duration: str,
        bail: str,
        channel: discord.TextChannel
    ):
        discord_line = (
            f"__**DISCORD:**__ {user.mention}\n"
            f"__**USER ID:**__ `{user.id}`\n\n"
            if user else
            "__**DISCORD:**__ *Not linked*\n\n"
        )

        embed = discord.Embed(
            title="🎮 Gamertag Ban Notification 🎮",
            description=(
                f"__**GAMERTAG:**__ `{gamertag}`\n\n"
                f"{discord_line}"
                f"__**REASON:**__ [{reason}](https://discord.com/channels/1109306235808911360/1109306236903633001)\n"
                f"__**DURATION:**__ `{duration}`\n"
                f"__**BAIL AMOUNT:**__ `{bail}`\n\n"
                "__**Paying Bail:**__\n"
                "*To pay your bail, make a ticket in* "
                "https://discord.com/channels/1109306235808911360/1109306236903633003 "
                '*under the option* __"Pay Bail"__\n\n'
                "__**Ban Appeals:**__\n"
                "*To appeal your ban, make a ticket in* "
                "https://discord.com/channels/1109306235808911360/1109306236903633003 "
                '*under the option* __"Support"__'
            ),
            color=random.randint(0, 0xFFFFFF),
            timestamp=discord.utils.utcnow()
        )

        embed.set_footer(
            text="DayZ Manager",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )

        embed.set_image(
            url="https://i.makeagif.com/media/12-20-2014/Lo3Taj.gif"
        )

        await channel.send(embed=embed)

        await interaction.response.send_message(
            f"✅ **Gamertag ban notification sent to {channel.mention}**",
            ephemeral=True
        )

    # 🔔 Friendly permission error
    @ban_gamertag.error
    async def ban_gamertag_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                "❌ You must be **Staff or Admin** to use this command.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(GamertagBan(bot))
