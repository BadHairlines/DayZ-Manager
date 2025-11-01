import discord
from discord import app_commands
from discord.ext import commands
from cogs.utils import (
    FLAGS, MAP_DATA, release_flag,
    db_pool, create_flag_embed
)


class Release(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def make_embed(self, title: str, desc: str, color: int) -> discord.Embed:
        """Helper for consistent release notifications."""
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name="🪧 Release Notification 🪧")
        embed.set_footer(
            text="DayZ Manager",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )
        return embed

    async def flag_autocomplete(self, interaction: discord.Interaction, current: str):
        """Autocomplete flag names."""
        return [
            app_commands.Choice(name=flag, value=flag)
            for flag in FLAGS if current.lower() in flag.lower()
        ][:25]

    async def update_flag_message(self, guild: discord.Guild, guild_id: str, map_key: str):
        """Refresh the live flag embed message after release."""
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                guild_id, map_key
            )
        if not row:
            return

        channel = guild.get_channel(int(row["channel_id"]))
        if not channel:
            return

        try:
            msg = await channel.fetch_message(int(row["message_id"]))
            embed = await create_flag_embed(guild_id, map_key)
            await msg.edit(embed=embed)
        except Exception as e:
            print(f"⚠️ Failed to update flag message: {e}")

    @app_commands.command(
        name="release",
        description="Release a flag back to ✅ for a specific map."
    )
    @app_commands.describe(selected_map="Select the map", flag="Flag to release")
    @app_commands.choices(selected_map=[
        app_commands.Choice(name="Livonia", value="livonia"),
        app_commands.Choice(name="Chernarus", value="chernarus"),
        app_commands.Choice(name="Sakhal", value="sakhal"),
    ])
    @app_commands.autocomplete(flag=flag_autocomplete)
    async def release(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str],
        flag: str
    ):
        """Releases a claimed flag back to ✅ available."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You must be an administrator to use this command.",
                ephemeral=True
            )
            return

        guild_id = str(interaction.guild.id)
        map_key = selected_map.value

        # ✅ Release flag in DB
        await release_flag(guild_id, map_key, flag)

        # ✅ Confirmation embed
        embed = self.make_embed(
            "**FLAG RELEASED**",
            f"✅ The **{flag}** flag has been released and is now available again "
            f"on **{MAP_DATA[map_key]['name']}**.",
            0x00FF00
        )
        await interaction.response.send_message(embed=embed)

        # 🔁 Update the live flag message
        await self.update_flag_message(interaction.guild, guild_id, map_key)


async def setup(bot: commands.Bot):
    await bot.add_cog(Release(bot))
