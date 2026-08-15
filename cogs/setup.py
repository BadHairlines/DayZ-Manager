import discord
from discord import app_commands, Interaction, Embed
from discord.ext import commands

from cogs import utils
from cogs.helpers.decorators import (
    admin_only,
    MAP_CHOICES,
    normalize_map
)
from cogs.ui_views import FlagManageView


class Setup(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def get_or_create_category(
        self,
        guild,
        name,
        reason
    ):
        category = discord.utils.get(
            guild.categories,
            name=name
        )

        if category:
            return category

        return await guild.create_category(
            name=name,
            reason=reason
        )

    async def get_or_create_text_channel(
        self,
        guild,
        name,
        category,
        reason,
        seed_message=None
    ):
        channel = discord.utils.get(
            guild.text_channels,
            name=name
        )

        if channel:
            return channel

        channel = await guild.create_text_channel(
            name=name,
            category=category,
            reason=reason
        )

        if seed_message:
            await channel.send(seed_message)

        return channel

    @app_commands.command(
        name="setup",
        description="Set up the flag system for a server."
    )
    @admin_only()
    @app_commands.choices(selected_map=MAP_CHOICES)
    @app_commands.describe(
        selected_map="Map for this flag system.",
        server="Server name/identifier, e.g. Livonia #1"
    )
    async def setup(
        self,
        interaction: Interaction,
        selected_map: app_commands.Choice[str],
        server: str
    ):

        if not interaction.guild:
            return await interaction.response.send_message(
                "❌ Server only.",
                ephemeral=True
            )

        server = utils.normalize_server(server)

        if not server:
            return await interaction.response.send_message(
                "❌ You must provide a server name.",
                ephemeral=True
            )

        if len(server) > 50:
            return await interaction.response.send_message(
                "❌ Server name must be 50 characters or less.",
                ephemeral=True
            )

        guild = interaction.guild
        guild_id = str(guild.id)

        map_key = normalize_map(
            selected_map.value
        )

        map_info = utils.MAP_DATA.get(map_key)

        if not map_info:
            return await interaction.response.send_message(
                "❌ Invalid map.",
                ephemeral=True
            )

        await interaction.response.send_message(
            f"⚙️ Setting up **{map_info['name']} — {server}**...",
            ephemeral=True
        )

        try:

            await utils.ensure_connection()

            # ---------------------------------
            # CHECK EXISTING SETUP
            # ---------------------------------
            async with utils.safe_acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT channel_id, message_id
                    FROM flag_messages
                    WHERE guild_id=$1
                      AND map=$2
                      AND server=$3
                    """,
                    guild_id,
                    map_key,
                    server
                )

            # ---------------------------------
            # CATEGORY
            # ---------------------------------
            category = await self.get_or_create_category(
                guild,
                f"🌍 {map_info['name']} — {server}",
                "Flag System Setup"
            )

            # Discord channel names cannot contain spaces
            channel_name = (
                f"flags-{map_key}-"
                f"{server.replace(' ', '-').lower()}"
            )

            # Keep channel name reasonable
            channel_name = channel_name[:100]

            channel = await self.get_or_create_text_channel(
                guild,
                channel_name,
                category,
                "Flag System Setup",
                seed_message=(
                    f"📜 **{map_info['name']} Flag System Initialized**\n"
                    f"🖥️ Server: **{server}**"
                )
            )

            # ---------------------------------
            # INITIALIZE FLAGS
            # ---------------------------------
            for flag in utils.FLAGS:

                await utils.set_flag(
                    guild_id,
                    map_key,
                    server,
                    flag,
                    "✅",
                    None
                )

            # ---------------------------------
            # CREATE EMBED
            # ---------------------------------
            embed = await utils.create_flag_embed(
                guild_id,
                map_key,
                server
            )

            view = FlagManageView(
                guild,
                map_key,
                server,
                self.bot
            )

            message = None

            # ---------------------------------
            # UPDATE EXISTING MESSAGE
            # ---------------------------------
            if row:

                try:

                    old_channel = self.bot.get_channel(
                        int(row["channel_id"])
                    )

                    if old_channel:

                        message = await old_channel.fetch_message(
                            int(row["message_id"])
                        )

                        await message.edit(
                            embed=embed,
                            view=view
                        )

                except (
                    discord.NotFound,
                    discord.Forbidden,
                    discord.HTTPException
                ):
                    message = None

            # ---------------------------------
            # CREATE MESSAGE
            # ---------------------------------
            if message is None:

                message = await channel.send(
                    embed=embed,
                    view=view
                )

            # ---------------------------------
            # SAVE MESSAGE
            # ---------------------------------
            async with utils.safe_acquire() as conn:

                await conn.execute(
                    """
                    INSERT INTO flag_messages (
                        guild_id,
                        map,
                        server,
                        channel_id,
                        message_id
                    )

                    VALUES ($1, $2, $3, $4, $5)

                    ON CONFLICT (
                        guild_id,
                        map,
                        server
                    )

                    DO UPDATE SET
                        channel_id = EXCLUDED.channel_id,
                        message_id = EXCLUDED.message_id
                    """,
                    guild_id,
                    map_key,
                    server,
                    str(channel.id),
                    str(message.id)
                )

            # ---------------------------------
            # COMPLETE
            # ---------------------------------
            await interaction.edit_original_response(
                embed=Embed(
                    title="SETUP COMPLETE",
                    description=(
                        f"✅ **{map_info['name']}** is ready.\n\n"
                        f"🖥️ **Server:** `{server}`\n"
                        f"📍 **Channel:** {channel.mention}"
                    ),
                    color=discord.Color.green()
                )
            )

        except Exception as e:

            await interaction.edit_original_response(
                content=(
                    f"❌ Setup failed:\n"
                    f"`{type(e).__name__}: {e}`"
                )
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Setup(bot))
