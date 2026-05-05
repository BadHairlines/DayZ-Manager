import discord
from discord import app_commands, Interaction, Embed
from discord.ext import commands

from cogs import utils
from cogs.helpers.decorators import admin_only, MAP_CHOICES, normalize_map


class Setup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def get_or_create_category(self, guild, name, reason):
        category = discord.utils.get(guild.categories, name=name)
        if category:
            return category

        return await guild.create_category(name=name, reason=reason)

    async def get_or_create_text_channel(self, guild, name, category, reason, seed_message=None):
        channel = discord.utils.get(guild.text_channels, name=name)

        if channel:
            return channel

        channel = await guild.create_text_channel(
            name=name,
            category=category,
            reason=reason,
        )

        if seed_message:
            await channel.send(seed_message)

        return channel

    @app_commands.command(name="setup")
    @admin_only()
    @app_commands.choices(selected_map=MAP_CHOICES)
    async def setup(self, interaction: Interaction, selected_map: app_commands.Choice[str]):
        if not interaction.guild:
            return await interaction.response.send_message(
                "❌ Server only.",
                ephemeral=True
            )

        guild = interaction.guild
        guild_id = str(guild.id)

        map_key = normalize_map(selected_map.value)
        map_info = utils.MAP_DATA.get(map_key)

        if not map_info:
            return await interaction.response.send_message(
                "❌ Invalid map.",
                ephemeral=True
            )

        await interaction.response.send_message(
            f"⚙️ Setting up **{map_info['name']}** flag system...",
            ephemeral=True,
        )

        await utils.ensure_connection()

        try:
            # -----------------------------
            # FETCH EXISTING MESSAGE DATA
            # -----------------------------
            async with utils.safe_acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT channel_id, message_id
                    FROM flag_messages
                    WHERE guild_id=$1 AND map=$2
                    """,
                    guild_id,
                    map_key
                )

            # -----------------------------
            # SETUP CATEGORY
            # -----------------------------
            category = await self.get_or_create_category(
                guild,
                f"🌍 {map_info['name']} Flag System",
                "Flag System Setup",
            )

            # -----------------------------
            # SETUP CHANNEL
            # -----------------------------
            channel = await self.get_or_create_text_channel(
                guild,
                f"flags-{map_key}",
                category,
                "Flag System Setup",
                seed_message=f"📜 {map_info['name']} Flag System Initialized",
            )

            # -----------------------------
            # RESET FLAGS
            # -----------------------------
            for flag in utils.FLAGS:
                await utils.set_flag(guild_id, map_key, flag, "✅", None)

            embed = await utils.create_flag_embed(guild_id, map_key)

            message = None

            # -----------------------------
            # UPDATE EXISTING MESSAGE IF POSSIBLE
            # -----------------------------
            if row:
                try:
                    old_channel = self.bot.get_channel(int(row["channel_id"]))

                    if old_channel:
                        message = await old_channel.fetch_message(int(row["message_id"]))
                        await message.edit(embed=embed)

                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    message = None

            # -----------------------------
            # CREATE NEW MESSAGE IF NEEDED
            # -----------------------------
            if message is None:
                message = await channel.send(embed=embed)

            # -----------------------------
            # SAVE TO DATABASE
            # -----------------------------
            async with utils.safe_acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO flag_messages (guild_id, map, channel_id, message_id)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (guild_id, map)
                    DO UPDATE SET
                        channel_id = EXCLUDED.channel_id,
                        message_id = EXCLUDED.message_id
                    """,
                    guild_id,
                    map_key,
                    str(channel.id),
                    str(message.id),
                )

            # -----------------------------
            # FINAL RESPONSE
            # -----------------------------
            await interaction.edit_original_response(
                embed=Embed(
                    title="SETUP COMPLETE",
                    description=f"✅ **{map_info['name']}** ready.",
                    color=discord.Color.green(),
                )
            )

        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ Setup failed: `{type(e).__name__}: {e}`"
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Setup(bot))
