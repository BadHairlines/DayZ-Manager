import discord
from discord.ext import commands
from discord import app_commands

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
        server_role="Optional role to show as the server in the embed",
        title="Event title",
        description="Embed description for the main body",
        location="Event location",
        kill_reward="Reward per kill",
        loadouts="Loadouts provided",
        final_prize="Final prize description",
        rules="Rules or warnings",
        image="Optional image file to include in the embed",
        color="Optional hex color code for the embed (e.g., #FF0000)",
        footer="Optional footer text"
    )
    @is_admin()
    async def role_dm(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        title: str,
        description: str,
        location: str,
        kill_reward: str,
        loadouts: str,
        final_prize: str,
        rules: str,
        server_role: discord.Role = None,
        image: discord.Attachment = None,
        color: str = "#0099ff",
        footer: str = None
    ):
        """DMs everyone in a role with a structured embed with multiple fields"""
        try:
            embed_color = discord.Color(int(color.strip("#"), 16))
        except:
            embed_color = discord.Color.blue()

        embed = discord.Embed(
            title=title,
            description=description,
            color=embed_color
        )

        embed.add_field(name=":round_pushpin: Location", value=location, inline=True)
        embed.add_field(name=":moneybag: Kill Reward", value=kill_reward, inline=True)
        embed.add_field(name=":gun: Loadouts", value=loadouts, inline=True)
        embed.add_field(name=":trophy: Final Prize", value=final_prize, inline=False)
        embed.add_field(name=":warning: Rules", value=rules, inline=False)

        if server_role:
            embed.add_field(name=":globe_with_meridians: Server", value=server_role.mention, inline=False)

        if image:
            embed.set_image(url=image.url)

        if footer:
            embed.set_footer(text=footer)

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

    # --- Autocomplete handlers for choices ---
    @role_dm.autocomplete("title")
    async def title_autocomplete(self, interaction: discord.Interaction, current: str):
        return [choice for choice in TITLE_CHOICES if current.lower() in choice.name.lower()]

    @role_dm.autocomplete("kill_reward")
    async def kill_reward_autocomplete(self, interaction: discord.Interaction, current: str):
        return [choice for choice in KILL_REWARD_CHOICES if current.lower() in choice.name.lower()]

    @role_dm.autocomplete("loadouts")
    async def loadouts_autocomplete(self, interaction: discord.Interaction, current: str):
        return [choice for choice in LOADOUT_CHOICES if current.lower() in choice.name.lower()]


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleDM(bot))
