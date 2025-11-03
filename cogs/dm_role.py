import discord
from discord import app_commands
from discord.ext import commands

class DMRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="dm-role",
        description="DM everyone in a specific role a plain message (supports invite links, no embeds)."
    )
    @app_commands.describe(
        role="Select the role whose members you want to message",
        message="The message to send to all members in that role"
    )
    async def dm_role(self, interaction: discord.Interaction, role: discord.Role, message: str):
        # 🔒 Only admins
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Only admins can use this command.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        sent = 0
        failed = 0
        skipped = 0

        for member in role.members:
            if member.bot:
                skipped += 1
                continue
            try:
                # Send as raw text — not an embed
                await member.send(message)
                sent += 1
            except discord.Forbidden:
                failed += 1
            except Exception as e:
                print(f"⚠️ Could not DM {member}: {e}")
                failed += 1

        summary = (
            f"📨 **DM Summary for {role.name}**\n"
            f"✅ Sent: `{sent}`\n"
            f"⚠️ Failed: `{failed}`\n"
            f"🤖 Skipped bots: `{skipped}`"
        )
        await interaction.followup.send(summary, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(DMRole(bot))
