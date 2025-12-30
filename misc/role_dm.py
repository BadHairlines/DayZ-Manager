import discord
from discord.ext import commands
from discord import app_commands

# --- Predefined choices ---
TITLE_CHOICES = [
    app_commands.Choice(name="King Of The Hill", value="King Of The Hill"),
    app_commands.Choice(name="Fight Night", value="Fight Night"),
    app_commands.Choice(name="Battle Royale", value="Battle Royale"),
    app_commands.Choice(name="Swords vs Swords", value="Swords vs Swords")
]

KILL_REWARD_CHOICES = [
    app_commands.Choice(name="50,000", value="50,000"),
    app_commands.Choice(name="100,000", value="100,000"),
    app_commands.Choice(name="150,000", value="150,000"),
    app_commands.Choice(name="200,000", value="200,000")
]

LOADOUT_CHOICES = [
    app_commands.Choice(name="Provided", value="Provided"),
    app_commands.Choice(name="Not Provided", value="Not Provided")
]

SERVER_CHOICES = [
    app_commands.Choice(name="50x - Chernarus", value="50x - Chernarus"),
    app_commands.Choice(name="50x - Livonia", value="50x - Livonia")
]

class RoleDM(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Admin-only check
    def is_admin():
        async def predicate(interaction: discord.Interaction):
            return interaction.user.guild_permissions.administrator
        return app_commands.check(predicate)

    @app_commands.command(
        name="role_dm",
        description="DM everyone in a role with a rich embed (Admin Only)"
    )
    @app_commands.describe(
        role="The role to DM",
        server="Select the server",
        title="Event title",
        start_time="Start time (Unix timestamp, e.g. 1767092438)",
        description="Embed description for the main body",
        location="Event location",
        kill_reward="Reward per kill",
        loadouts="Loadouts provided",
        rules="Rules or warnings",
        image="Optional image file to include in the embed"
    )
    @is_admin()
    async def role_dm(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        title: str,
        start_time: str,
        description: str,
        location: str,
        kill_reward: str,
        loadouts: str,
        rules: str,
        server: str,
        image: discord.Attachment = None
    ):
        """DMs everyone in a role with a structured embed with multiple fields"""

        # Hardcoded Hive yellow color and footer
        embed_color = discord.Color.from_rgb(255, 204, 0)  # Hive yellow
        embed_footer = "The Hive - 50x Servers"

        # Add start time to title
        embed_title = f"`{title}` - <t:{start_time}:R>"

        embed = discord.Embed(
            title=embed_title,
            description=description,
            color=embed_color
        )

        embed.add_field(name=":round_pushpin: Location", value=f"`{location}`", inline=True)
        embed.add_field(name=":moneybag: Kill Reward", value=f"`{kill_reward}`", inline=True)
        embed.add_field(name=":gun: Loadouts", value=f"`{loadouts}`", inline=True)
        embed.add_field(name=":warning: Rules", value=f"`{rules}`", inline=False)
        embed.add_field(name=":globe_with_meridians: Server", value=f"`{server}`", inline=False)
        embed.add_field(name="\u200b", value="[The Hive™ - DayZ Community](https://discord.com/invite/thehivedayz)", inline=False)

        if image:
            embed.set_image(url=image.url)

        embed.set_footer(text=embed_footer)

        sent_count = 0
        failed_count = 0
        for member in role.members:
            try:
                await member.send(embed=embed)
                sent_count += 1
            except:
                failed_count += 1

        await interaction.response.send_message(
            f"✅ Embed sent to {sent_count} members. Failed to send to {failed_count}.",
            ephemeral=True
        )

    # --- Autocomplete handlers ---
    @role_dm.autocomplete("title")
    async def title_autocomplete(self, interaction: discord.Interaction, current: str):
        return [c for c in TITLE_CHOICES if current.lower() in c.name.lower()]

    @role_dm.autocomplete("kill_reward")
    async def kill_reward_autocomplete(self, interaction: discord.Interaction, current: str):
        return [c for c in KILL_REWARD_CHOICES if current.lower() in c.name.lower()]

    @role_dm.autocomplete("loadouts")
    async def loadouts_autocomplete(self, interaction: discord.Interaction, current: str):
        return [c for c in LOADOUT_CHOICES if current.lower() in c.name.lower()]

    @role_dm.autocomplete("server")
    async def server_autocomplete(self, interaction: discord.Interaction, current: str):
        return [c for c in SERVER_CHOICES if current.lower() in c.name.lower()]


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleDM(bot))
