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
        title="Embed title",
        description="Embed description with emojis and formatting",
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
        image: discord.Attachment = None,
        color: str = "#0099ff",
        footer: str = None
    ):
        """DMs everyone in a role with a formatted embed"""
        try:
            embed_color = discord.Color(int(color.strip("#"), 16))
        except:
            embed_color = discord.Color.blue()

        embed = discord.Embed(
            title=title,
            description=description,
            color=embed_color
        )

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

async def setup(bot: commands.Bot):
    await bot.add_cog(RoleDM(bot))
