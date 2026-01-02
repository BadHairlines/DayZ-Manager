import discord
from discord import app_commands
from discord.ext import commands

# ─── CONSTANTS ──────────────────────────────────────────────────────────────

STAFF_ROLE_ID = 1109306236110909567

TICKET_CHANNEL_URL = "https://discord.com/channels/1109306235808911360/1109306236903633003"
REASON_LINK = "https://discord.com/channels/1109306235808911360/1109306236903633001"

EMBED_COLOR = discord.Color.red()
FOOTER_ICON = "https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
BANNER_GIF = "https://i.makeagif.com/media/12-20-2014/Lo3Taj.gif"

# ─── DROPDOWN CHOICES ────────────────────────────────────────────────────────

REASON_CHOICES = [
    app_commands.Choice(name="Harassment / Threats", value="Harassment / Threats"),
    app_commands.Choice(name="Hate Speech / Slurs", value="Hate Speech / Slurs"),
    app_commands.Choice(name="Spamming / Advertising", value="Spamming / Advertising"),
    app_commands.Choice(name="Staff Disrespect", value="Staff Disrespect"),
    app_commands.Choice(name="Impersonation", value="Impersonation"),
    app_commands.Choice(name="Ban Evasion", value="Ban Evasion"),
    app_commands.Choice(name="Scamming / Fraud", value="Scamming / Fraud"),
    app_commands.Choice(name="NSFW / Inappropriate Content", value="NSFW / Inappropriate Content"),
    app_commands.Choice(name="Other (See Rules)", value="Other (See Rules)"),
]

DURATION_CHOICES = [
    app_commands.Choice(name="6 Hours", value="6h"),
    app_commands.Choice(name="12 Hours", value="12h"),
    app_commands.Choice(name="1 Day", value="1 day"),
    app_commands.Choice(name="2 Days", value="2 days"),
    app_commands.Choice(name="3 Days", value="3 days"),
    app_commands.Choice(name="7 Days", value="7 days"),
    app_commands.Choice(name="Permanent", value="Permanent"),
]

BAIL_CHOICES = [
    app_commands.Choice(name="1,000,000", value="1,000,000"),
    app_commands.Choice(name="2,500,000", value="2,500,000"),
    app_commands.Choice(name="5,000,000", value="5,000,000"),
    app_commands.Choice(name="10,000,000", value="10,000,000"),
    app_commands.Choice(name="25,000,000", value="25,000,000"),
]

# ─── PERMISSION CHECK ────────────────────────────────────────────────────────

def staff_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        member = interaction.user

        if not isinstance(member, discord.Member):
            return False

        if member.guild_permissions.administrator:
            return True

        return any(role.id == STAFF_ROLE_ID for role in member.roles)

    return app_commands.check(predicate)

# ─── COG ─────────────────────────────────────────────────────────────────────

class DiscordBan(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="ban_discord",
        description="Send a Discord ban notification embed"
    )
    @staff_only()
    @app_commands.describe(
        user="Banned user",
        reason="Reason for the ban",
        duration="Ban duration",
        bail="Bail amount",
        channel="Channel to send the ban notice (optional)"
    )
    @app_commands.choices(
        reason=REASON_CHOICES,
        duration=DURATION_CHOICES,
        bail=BAIL_CHOICES
    )
    async def ban_discord(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        reason: app_commands.Choice[str],
        duration: app_commands.Choice[str],
        bail: app_commands.Choice[str],
        channel: discord.TextChannel | None = None
    ):
        channel = channel or interaction.channel

        # 🚫 Disable bail if Permanent
        is_permanent = duration.value.lower() == "permanent"
        final_bail = "N/A (Permanent Ban)" if is_permanent else bail.value

        embed = discord.Embed(
            title="🔨 Discord Ban Notification",
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )

        embed.add_field(
            name="User",
            value=f"{user.mention}\n`{user.id}`",
            inline=False
        )

        embed.add_field(
            name="Reason",
            value=f"[{reason.value}]({REASON_LINK})",
            inline=False
        )

        embed.add_field(name="Duration", value=duration.value, inline=True)
        embed.add_field(name="Bail Amount", value=final_bail, inline=True)

        embed.add_field(
            name="Paying Bail",
            value=(
                "Bail is not available for permanent bans."
                if is_permanent else
                f"Create a ticket in {TICKET_CHANNEL_URL}\n"
                'Select **"Pay Bail"**'
            ),
            inline=False
        )

        embed.add_field(
            name="Ban Appeals",
            value=(
                f"Create a ticket in {TICKET_CHANNEL_URL}\n"
                'Select **"Support"**'
            ),
            inline=False
        )

        embed.set_footer(text="DayZ Manager", icon_url=FOOTER_ICON)
        embed.set_image(url=BANNER_GIF)

        await channel.send(embed=embed)

        notice = (
            "⚠️ Permanent ban selected — bail was automatically disabled."
            if is_permanent else
            f"✅ Ban notification sent to {channel.mention}"
        )

        if interaction.response.is_done():
            await interaction.followup.send(notice, ephemeral=True)
        else:
            await interaction.response.send_message(notice, ephemeral=True)

    # ─── ERRORS ────────────────────────────────────────────────────────────

    @ban_discord.error
    async def ban_discord_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError
    ):
        msg = (
            "❌ You must be **Staff or Admin** to use this command."
            if isinstance(error, app_commands.CheckFailure)
            else "❌ Something went wrong while running this command."
        )

        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(DiscordBan(bot))
