import discord
from discord import app_commands
from discord.ext import commands

class RoleDM(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="role_dm",
        description="ADMIN ONLY: DM everyone in a role with an embed"
    )
    @app_commands.describe(
        role="Role to DM",
        title="Embed title",
        message="Embed message",
        color="Embed color (hex, optional)"
    )
    async def role_dm(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        title: str,
        message: str,
        color: str = "2F3136"
    ):
        # 🔒 HARD ADMIN CHECK
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ This command is **Administrator only**.",
                ephemeral=True
            )

        await interaction.response.send_message(
            f"📨 Sending DMs to **{len(role.members)}** members...",
            ephemeral=True
        )

        # Embed color handling
        try:
            embed_color = int(color.replace("#", ""), 16)
        except ValueError:
            embed_color = 0x2F3136

        embed = discord.Embed(
            title=title,
            description=message,
            color=embed_color
        )
        embed.set_footer(text=interaction.guild.name)

        sent = 0
        failed = 0

        for member in role.members:
            if member.bot:
                continue

            try:
                await member.send(embed=embed)
                sent += 1
            except discord.Forbidden:
                failed += 1
            except Exception:
                failed += 1

        await interaction.followup.send(
            f"✅ **Role DM Complete**\n"
            f"📬 Sent: **{sent}**\n"
            f"❌ Failed: **{failed}**",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(RoleDM(bot))
