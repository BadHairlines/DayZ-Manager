import discord
from discord.ext import commands
from discord import app_commands

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
        title="Event title",
        start_time="Start time (Unix timestamp, e.g. 1767092438)",
        description="Embed description for the main body",
        location="Event location",
        kill_reward="Reward per kill",
        loadouts="Loadouts provided",
        rules="Rules or warnings",
        server="Server name",
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
        
        # Hardcoded Hive yellow color
        embed_color = discord.Color.from_rgb(255, 204, 0)  # Hive yellow
        
        # Embed title with start time
        embed_title = f"`{title} - <t:{start_time}:R>`"

        embed = discord.Embed(
            title=embed_title,
            description=description,
            color=embed_color
        )

        # Embed fields
        embed.add_field(name=":round_pushpin: Location", value=f"`{location}`", inline=True)
        embed.add_field(name=":moneybag: Kill Reward", value=f"`{kill_reward}`", inline=True)
        embed.add_field(name=":gun: Loadouts", value=f"`{loadouts}`", inline=True)
        embed.add_field(name=":warning: Rules", value=f"`{rules}`", inline=True)
        embed.add_field(name=":globe_with_meridians: Server", value=f"`{server}`", inline=True)

        # Set image if provided
        if image:
            embed.set_image(url=image.url)

        # Hardcoded footer
        embed.set_footer(text="The Hive - 50x Servers")

        # Send DM to each member in the role
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

async def setup(bot: commands.Bot):
    await bot.add_cog(RoleDM(bot))
