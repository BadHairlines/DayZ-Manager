import asyncio
import discord
from discord import app_commands, Interaction, Embed
from discord.ext import commands

from dayz_manager.config import MAP_DATA, FLAGS as ALL_FLAGS
from dayz_manager.cogs.utils.database import db_pool
from dayz_manager.cogs.utils.embeds import create_flag_embed
from dayz_manager.cogs.utils.logging import log_action
from dayz_manager.cogs.helpers.decorators import admin_only, MAP_CHOICES, normalize_map
from dayz_manager.cogs.flags.ui import FlagManageView

class Setup(commands.Cog):
    """Handles setup and initialization of flag systems per map."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Setup or refresh a map and initialize all flags in the database.")
    @admin_only()
    @app_commands.describe(selected_map="Select the map to setup (Livonia, Chernarus, Sakhal)")
    @app_commands.choices(selected_map=MAP_CHOICES)
    async def setup(self, interaction: Interaction, selected_map: app_commands.Choice[str]):
        guild = interaction.guild
        guild_id = str(guild.id)
        map_key = normalize_map(selected_map)
        map_info = MAP_DATA[map_key]

        flags_channel_name = f"flags-{map_key}"
        logs_channel_name = f"{map_key}-logs"

        await interaction.response.send_message(f"⚙️ Setting up **{map_info['name']}** flags... please wait ⏳", ephemeral=True)

        if db_pool is None:
            return await interaction.followup.send("❌ Database not initialized. Please restart the bot.")

        try:
            async with db_pool.acquire() as conn:
                await conn.execute("""                    CREATE TABLE IF NOT EXISTS flag_messages (
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

            flags_channel = discord.utils.get(guild.text_channels, name=flags_channel_name)
            if not flags_channel:
                flags_channel = await guild.create_text_channel(name=flags_channel_name, reason=f"Auto-created for {map_info['name']} setup")
                await flags_channel.send(f"📜 Flag ownership for **{map_info['name']}**.")

            log_channel = discord.utils.get(guild.text_channels, name=logs_channel_name)
            if not log_channel:
                log_channel = await guild.create_text_channel(name=logs_channel_name, reason=f"Log channel for {map_info['name']} flag activity")
                await log_channel.send(f"🗒️ Logs for **{map_info['name']}** setup.")

            for flag in ALL_FLAGS:
                async with db_pool.acquire() as conn:
                    await conn.execute("""                        INSERT INTO flags (guild_id, map, flag, status, role_id)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (guild_id, map, flag)
                        DO UPDATE SET status = EXCLUDED.status, role_id = EXCLUDED.role_id;
                    """, guild_id, map_key, flag, "✅", None)
                await asyncio.sleep(0.02)

            embed = await create_flag_embed(guild_id, map_key)
            view = FlagManageView(guild, map_key, self.bot)

            msg = None
            if row:
                try:
                    old_channel = guild.get_channel(int(row["channel_id"]))
                    if old_channel:
                        msg = await old_channel.fetch_message(int(row["message_id"]))
                        await msg.edit(embed=embed, view=view)
                except Exception:
                    msg = None

            if not msg:
                msg = await flags_channel.send(embed=embed, view=view)

            async with db_pool.acquire() as conn:
                await conn.execute("""                    INSERT INTO flag_messages (guild_id, map, channel_id, message_id, log_channel_id)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (guild_id, map)
                    DO UPDATE SET channel_id = EXCLUDED.channel_id, message_id = EXCLUDED.message_id, log_channel_id = EXCLUDED.log_channel_id;
                """, guild_id, map_key, str(flags_channel.id), str(msg.id), str(log_channel.id))

            complete_embed = Embed(
                title="__SETUP COMPLETE__",
                description=(
                    f"✅ **{map_info['name']}** setup finished successfully.\n\n"
                    f"📁 Flags channel: {flags_channel.mention}\n"
                    f"🧭 Log channel: {log_channel.mention}\n"
                    f"🧾 Flag message refreshed.\n\n"
                    f"🟩 **Admins can manage flags below the embed!**"
                ), color=0x00FF00
            )
            complete_embed.set_image(url=map_info["image"])
            complete_embed.set_author(name="🚨 Setup Notification 🚨")
            complete_embed.set_footer(text="DayZ Manager • Interactive Flag Controls Enabled", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
            complete_embed.timestamp = discord.utils.utcnow()

            await interaction.edit_original_response(content=None, embed=complete_embed)

            await log_action(guild, map_key, title="Map Setup Complete", description=(
                f"✅ **{map_info['name']}** setup by {interaction.user.mention}.\n\n"
                f"📁 Flags: {flags_channel.mention}\n"
                f"🧭 Logs: {log_channel.mention}"
            ), color=0x2ECC71)

        except Exception as e:
            await interaction.edit_original_response(content=f"❌ Setup failed for **{map_info['name']}**:\n```{e}```")
            await log_action(guild, map_key, title="Setup Failed", description=f"❌ Setup failed for **{map_info['name']}**:\n```{e}```", color=0xE74C3C)

async def setup(bot: commands.Bot):
    await bot.add_cog(Setup(bot))
