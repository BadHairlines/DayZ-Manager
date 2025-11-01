import discord
from discord import app_commands
from discord.ext import commands

class MentionCategory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="mention-category", description="Mention every text channel inside a selected category.")
    @app_commands.describe(category="Select the category to mention all its channels.")
    async def mention_category(self, interaction: discord.Interaction, category: discord.CategoryChannel):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only admins can use this command!", ephemeral=True)
            return

        # Collect text channels and skip first 2
        text_channels = [ch for ch in category.channels if isinstance(ch, discord.TextChannel)][2:]

        if not text_channels:
            await interaction.response.send_message(f"⚠️ No text channels found in **{category.name}** (after skipping first two).", ephemeral=True)
            return

        # Put each mention on a new line
        mentions = "\n".join([ch.mention for ch in text_channels])
        message = f"📢 **Channels in {category.name}:**\n{mentions}"

        await interaction.response.send_message(message)

async def setup(bot):
    await bot.add_cog(MentionCategory(bot))
