from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from . import database


# =========================================================
# CONFIG
# =========================================================

BADLANDS_RELEASE = 1792022400

EMBED_COLOR = 0xD4A017

UPDATE_INTERVAL = 60


# =========================================================
# BADLANDS COUNTDOWN COG
# =========================================================

class BadlandsCountdown(commands.Cog):
    """
    Multi-server Badlands release countdown.

    Each Discord server can have its own countdown message.
    The countdown is stored in PostgreSQL so it survives
    bot restarts.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.update_countdowns.start()

    def cog_unload(self):
        self.update_countdowns.cancel()

    # =====================================================
    # DATABASE
    # =====================================================

    async def create_table(self):
        await database.execute(
            """
            CREATE TABLE IF NOT EXISTS badlands_countdowns (
                guild_id BIGINT PRIMARY KEY,
                channel_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )

    async def get_countdown(self, guild_id: int):
        return await database.fetchrow(
            """
            SELECT guild_id, channel_id, message_id
            FROM badlands_countdowns
            WHERE guild_id = $1
            """,
            guild_id,
        )

    async def save_countdown(
        self,
        guild_id: int,
        channel_id: int,
        message_id: int,
    ):
        await database.execute(
            """
            INSERT INTO badlands_countdowns (
                guild_id,
                channel_id,
                message_id
            )
            VALUES ($1, $2, $3)

            ON CONFLICT (guild_id)
            DO UPDATE SET
                channel_id = EXCLUDED.channel_id,
                message_id = EXCLUDED.message_id
            """,
            guild_id,
            channel_id,
            message_id,
        )

    async def delete_countdown(self, guild_id: int):
        await database.execute(
            """
            DELETE FROM badlands_countdowns
            WHERE guild_id = $1
            """,
            guild_id,
        )

    # =====================================================
    # EMBED
    # =====================================================

    def build_embed(self) -> discord.Embed:
        now = int(datetime.now(timezone.utc).timestamp())

        remaining = max(0, BADLANDS_RELEASE - now)

        days, remainder = divmod(remaining, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        if remaining > 0:

            countdown = (
                f"**{days} Days • "
                f"{hours} Hours • "
                f"{minutes} Minutes • "
                f"{seconds} Seconds**"
            )

            title = "🏜️ BADLANDS RELEASE COUNTDOWN"

            description = (
                "## 🏜️ BADLANDS IS COMING!\n\n"
                f"Badlands officially releases "
                f"**<t:{BADLANDS_RELEASE}:F>**.\n\n"
                "⏳ **TIME REMAINING**\n"
                f"{countdown}\n\n"
                f"📅 <t:{BADLANDS_RELEASE}:R>\n\n"
                "🔥 **GET READY.**"
            )

        else:

            title = "🏜️ BADLANDS HAS RELEASED!"

            description = (
                "## 🔥 BADLANDS IS HERE!\n\n"
                "Badlands has officially released!\n\n"
                f"📅 Released <t:{BADLANDS_RELEASE}:F>\n\n"
                "🐝 **THE HIVE IS READY.**"
            )

        embed = discord.Embed(
            title=title,
            description=description,
            color=EMBED_COLOR,
        )

        embed.set_footer(
            text="THE HIVE • BADLANDS"
        )

        return embed

    # =====================================================
    # SETUP COMMAND
    # =====================================================

    @app_commands.command(
        name="badlands-countdown",
        description="Set up the Badlands release countdown in this channel.",
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def badlands_countdown(
        self,
        interaction: discord.Interaction,
    ):

        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        guild_id = interaction.guild.id
        channel = interaction.channel

        if not isinstance(
            channel,
            (
                discord.TextChannel,
                discord.Thread,
                discord.VoiceChannel,
            ),
        ):
            await interaction.followup.send(
                "❌ This channel cannot be used for the countdown.",
                ephemeral=True,
            )
            return

        # Make sure database table exists
        await self.create_table()

        # Check if this server already has one
        existing = await self.get_countdown(
            guild_id
        )

        if existing:

            await interaction.followup.send(
                "⚠️ This server already has a Badlands countdown.\n\n"
                "Use `/badlands-countdown refresh` "
                "if you want to recreate it.",
                ephemeral=True,
            )

            return

        # -------------------------------------------------
        # SEND EMBED
        # -------------------------------------------------

        try:

            message = await channel.send(
                embed=self.build_embed()
            )

        except discord.Forbidden:

            await interaction.followup.send(
                "❌ I don't have permission to send messages "
                "or embeds in this channel.",
                ephemeral=True,
            )

            return

        # -------------------------------------------------
        # SAVE
        # -------------------------------------------------

        await self.save_countdown(
            guild_id=guild_id,
            channel_id=channel.id,
            message_id=message.id,
        )

        await interaction.followup.send(
            f"✅ Badlands countdown created in {channel.mention}!",
            ephemeral=True,
        )

    # =====================================================
    # REMOVE COMMAND
    # =====================================================

    @app_commands.command(
        name="badlands-countdown-remove",
        description="Remove this server's Badlands countdown.",
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def badlands_countdown_remove(
        self,
        interaction: discord.Interaction,
    ):

        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        await self.create_table()

        existing = await self.get_countdown(
            interaction.guild.id
        )

        if not existing:

            await interaction.followup.send(
                "❌ This server doesn't have a Badlands countdown.",
                ephemeral=True,
            )

            return

        # Try deleting the actual Discord message
        channel = self.bot.get_channel(
            existing["channel_id"]
        )

        if channel:

            try:

                message = await channel.fetch_message(
                    existing["message_id"]
                )

                await message.delete()

            except (
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException,
            ):
                pass

        await self.delete_countdown(
            interaction.guild.id
        )

        await interaction.followup.send(
            "✅ Badlands countdown removed.",
            ephemeral=True,
        )

    # =====================================================
    # REFRESH COMMAND
    # =====================================================

    @app_commands.command(
        name="badlands-countdown-refresh",
        description="Refresh/recreate this server's Badlands countdown.",
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def badlands_countdown_refresh(
        self,
        interaction: discord.Interaction,
    ):

        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        await self.create_table()

        existing = await self.get_countdown(
            interaction.guild.id
        )

        if not existing:

            await interaction.followup.send(
                "❌ This server doesn't have a Badlands countdown yet.\n\n"
                "Use `/badlands-countdown` first.",
                ephemeral=True,
            )

            return

        channel = self.bot.get_channel(
            existing["channel_id"]
        )

        if channel is None:

            await self.delete_countdown(
                interaction.guild.id
            )

            await interaction.followup.send(
                "❌ The old countdown channel no longer exists. "
                "Run `/badlands-countdown` again.",
                ephemeral=True,
            )

            return

        # Delete old message
        try:

            old_message = await channel.fetch_message(
                existing["message_id"]
            )

            await old_message.delete()

        except (
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException,
        ):
            pass

        # Create new message
        try:

            new_message = await channel.send(
                embed=self.build_embed()
            )

        except discord.Forbidden:

            await interaction.followup.send(
                "❌ I don't have permission to send messages "
                "or embeds in the countdown channel.",
                ephemeral=True,
            )

            return

        await self.save_countdown(
            guild_id=interaction.guild.id,
            channel_id=channel.id,
            message_id=new_message.id,
        )

        await interaction.followup.send(
            "✅ Badlands countdown refreshed!",
            ephemeral=True,
        )

    # =====================================================
    # AUTOMATIC UPDATE LOOP
    # =====================================================

    @tasks.loop(seconds=UPDATE_INTERVAL)
    async def update_countdowns(self):

        if not self.bot.is_ready():
            return

        try:
            await self.create_table()

            rows = await database.fetch(
                """
                SELECT guild_id, channel_id, message_id
                FROM badlands_countdowns
                """
            )

        except Exception as e:

            print(
                f"[BADLANDS] Database error: {e}"
            )

            return

        for row in rows:

            try:

                channel = self.bot.get_channel(
                    row["channel_id"]
                )

                if channel is None:

                    continue

                message = await channel.fetch_message(
                    row["message_id"]
                )

                await message.edit(
                    embed=self.build_embed()
                )

            except discord.NotFound:

                # Message was deleted.
                # Recreate it automatically.

                try:

                    new_message = await channel.send(
                        embed=self.build_embed()
                    )

                    await self.save_countdown(
                        guild_id=row["guild_id"],
                        channel_id=row["channel_id"],
                        message_id=new_message.id,
                    )

                    print(
                        f"[BADLANDS] Recreated countdown "
                        f"for guild {row['guild_id']}"
                    )

                except Exception as e:

                    print(
                        f"[BADLANDS] Could not recreate "
                        f"countdown: {e}"
                    )

            except discord.Forbidden:

                print(
                    f"[BADLANDS] Missing permissions in "
                    f"guild {row['guild_id']}"
                )

            except discord.HTTPException as e:

                print(
                    f"[BADLANDS] Discord error: {e}"
                )

            except Exception as e:

                print(
                    f"[BADLANDS] Unexpected error: {e}"
                )

    @update_countdowns.before_loop
    async def before_update_countdowns(self):
        await self.bot.wait_until_ready()


# =========================================================
# SETUP
# =========================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(
        BadlandsCountdown(bot)
    )
