# cogs/setup.py
from asyncio import sleep
import discord
from discord import app_commands, Interaction, Embed
from discord.ext import commands
from cogs.utils import (
    FLAGS, MAP_DATA, set_flag, create_flag_embed,
    log_action, ensure_connection, safe_acquire
)
from cogs.helpers.decorators import admin_only, MAP_CHOICES, normalize_map
from cogs.ui_views import FlagManageView


class Setup(commands.Cog):
    """Handles setup and initialization of flag systems per map."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- small helpers ----------
    async def _get_or_create_category(self, guild: discord.Guild, name: str, reason: str) -> discord.CategoryChannel:
        cat = discord.utils.get(guild.categories, name=name)
        if not cat:
            cat = await guild.create_category(name=name, reason=reason)
            # tiny pause avoids occasional race conditions with immediate child-creates
            await sleep(0.5)
        return cat

    async def _get_or_create_text_channel(
        self,
        guild: discord.Guild,
        name: str,
        category: discord.CategoryChannel,
        reason: str,
        seed_message: str | None = None,
    ) -> discord.TextChannel:
        ch = discord.utils.get(guild.text_channels, name=name)
        if not ch:
            ch = await guild.create_text_channel(name=name, category=category, reason=reason)
            if seed_message:
                await ch.send(seed_message)
            await sleep(0.2)
        return ch

    @app_commands.command(
        name="setup",
        description="Setup or refresh a map and initialize all flags in the database."
    )
    @admin_only()
    @app_commands.describe(selected_map="Select the map to setup (Livonia, Chernarus, Sakhal)")
    @app_commands.choices(selected_map=MAP_CHOICES)
    async def setup(self, interaction: Interaction, selected_map: app_commands.Choice[str]):
        guild = interaction.guild
        guild_id = str(guild.id)
        map_key = normalize_map(selected_map)
        map_info = MAP_DATA[map_key]

        flags_channel_name = f"flags-{map_key}"
        logs_channel_name = f"flaglogs-{map_key}"

        await interaction.response.send_message(
            f"⚙️ Setting up **{map_info['name']}** flags... please wait ⏳",
            ephemeral=True
        )

        # Ensure DB is live and migrations/tables exist
        await ensure_connection()

        try:
            # Ensure the metadata table exists and fetch any previous message location
            async with safe_acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS flag_messages (
                        guild_id TEXT NOT NULL,
                        map TEXT NOT NULL,
                        channel_id TEXT NOT NULL,
                        message_id TEXT NOT NULL,
                        log_channel_id TEXT,
                        PRIMARY KEY (guild_id, map)
                    );
                """)
                row = await conn.fetchrow(
                    "SELECT channel_id, message_id, log_channel_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                    guild_id, map_key
                )

            # ----- Logs category + channel (rename old if needed) -----
            logs_category = await self._get_or_create_category(
                guild, "📜 DayZ Manager Logs", "Auto-created universal DayZ Manager log category"
            )

            # If a legacy "{map}-logs" exists, rename it once
            old_logs_channel = discord.utils.get(guild.text_channels, name=f"{map_key}-logs")
            if old_logs_channel:
                try:
                    await old_logs_channel.edit(name=logs_channel_name)
                    log_channel = old_logs_channel
                except discord.Forbidden:
                    # No rename perms? keep using old channel
                    log_channel = old_logs_channel
                    print(f"⚠️ Missing permission to rename {old_logs_channel.name}.")
            else:
                log_channel = discord.utils.get(guild.text_channels, name=logs_channel_name)

            if not log_channel:
                log_channel = await self._get_or_create_text_channel(
                    guild,
                    logs_channel_name,
                    logs_category,
                    reason=f"Auto-created log channel for {map_info['name']} activity",
                    seed_message=f"🗒️ Logs for **{map_info['name']}** initialized."
                )

            # ----- Flags category + channel -----
            flags_category = await self._get_or_create_category(
                guild, "📁 DayZ Manager Flags", "Auto-created universal category for all flag embed channels"
            )
            flags_channel = await self._get_or_create_text_channel(
                guild,
                flags_channel_name,
                flags_category,
                reason=f"Auto-created for {map_info['name']} setup",
                seed_message=f"📜 Flag ownership for **{map_info['name']}**."
            )

            # Keep perms in sync with category defaults (optional but nice)
            await flags_channel.edit(sync_permissions=True)
            await log_channel.edit(sync_permissions=True)

            # ----- Reset flags to unclaimed for this map -----
            for flag in FLAGS:
                await set_flag(guild_id, map_key, flag, "✅", None)
                await sleep(0.02)  # tiny yield to avoid bursty DB writes

            # ----- Build (or update) the live embed + persistent view -----
            embed = await create_flag_embed(guild_id, map_key)
            view = FlagManageView(guild, map_key, self.bot)

            msg = None
            if row:
                old_channel = guild.get_channel(int(row["channel_id"]))
                if old_channel:
                    try:
                        msg = await old_channel.fetch_message(int(row["message_id"]))
                        await msg.edit(embed=embed, view=view)
                    except discord.NotFound:
                        msg = None  # message was deleted
                    except discord.Forbidden:
                        msg = None  # no perms to edit; we'll post a new one

            if not msg:
                msg = await flags_channel.send(embed=embed, view=view)

            # Persist the location for this map’s message
            async with safe_acquire() as conn:
                await conn.execute("""
                    INSERT INTO flag_messages (guild_id, map, channel_id, message_id, log_channel_id)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (guild_id, map)
                    DO UPDATE SET
                        channel_id = EXCLUDED.channel_id,
                        message_id = EXCLUDED.message_id,
                        log_channel_id = EXCLUDED.log_channel_id;
                """, guild_id, map_key, str(flags_channel.id), str(msg.id), str(log_channel.id))

            # ----- Final confirmation to the invoker -----
            complete_embed = Embed(
                title="__SETUP COMPLETE__",
                description=(
                    f"✅ **{map_info['name']}** setup finished successfully.\n\n"
                    f"📁 **Flags Category:** {flags_category.name}\n"
                    f"🏁 **Flags Channel:** {flags_channel.mention}\n"
                    f"🧭 **Logs Channel:** {log_channel.mention}\n"
                    f"🧾 Flag message refreshed.\n\n"
                    f"🟩 **Admins can manage flags below the embed!**"
                ),
                color=0x00FF00
            )
            complete_embed.set_image(url=map_info["image"])
            complete_embed.set_author(name="🚨 Setup Notification 🚨")
            complete_embed.set_footer(
                text="DayZ Manager • Interactive Flag Controls Enabled",
                icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
            )
            complete_embed.timestamp = discord.utils.utcnow()

            await interaction.edit_original_response(content=None, embed=complete_embed)

            await log_action(
                guild,
                map_key,
                title="Map Setup Complete",
                description=(
                    f"✅ **{map_info['name']}** setup by {interaction.user.mention}.\n\n"
                    f"📁 Category: {flags_category.name}\n"
                    f"🏁 Flags: {flags_channel.mention}\n"
                    f"🧭 Logs: {log_channel.mention}"
                ),
                color=0x2ECC71
            )

        except Exception as e:
            # User-facing error
            await interaction.edit_original_response(
                content=f"❌ Setup failed for **{map_info['name']}**:\n```{e}```"
            )
            # Logged error
            await log_action(
                guild,
                map_key,
                title="Setup Failed",
                description=f"❌ Setup failed for **{map_info['name']}**:\n```{e}```",
                color=0xE74C3C
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Setup(bot))
