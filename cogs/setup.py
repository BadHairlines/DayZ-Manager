import asyncio
import discord
from discord import app_commands, Interaction, Embed
from discord.ext import commands
from cogs.utils import FLAGS, MAP_DATA, set_flag, db_pool, create_flag_embed, log_action, ensure_connection
from cogs.helpers.decorators import admin_only, MAP_CHOICES, normalize_map
from cogs.ui_views import FlagManageView

class Setup(commands.Cog):
    """Handles setup and initialization of flag systems per map."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

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

        category_name = map_info["name"]
        flags_channel_name = f"flags-{map_key}"
        logs_channel_name = f"{map_key}-logs"

        await interaction.response.send_message(
            f"⚙️ Setting up **{map_info['name']}** flags... please wait ⏳",
            ephemeral=True
        )

        # 🧩 Ensure DB connected (auto-reconnect)
        await ensure_connection()

        try:
            # =============================
            # 🗃️ Ensure flag_messages table
            # =============================
            async with db_pool.acquire() as conn:
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

            # =============================
            # 📜 Universal Logs Category
            # =============================
            logs_category_name = "📜 DayZ Manager Logs"
            logs_category = discord.utils.get(guild.categories, name=logs_category_name)
            if not logs_category:
                logs_category = await guild.create_category(
                    name=logs_category_name,
                    reason="Auto-created universal DayZ Manager log category"
                )
                await asyncio.sleep(0.5)

            # ✅ Create or reuse per-map log channel inside universal category
            log_channel = discord.utils.get(guild.text_channels, name=logs_channel_name)
            if not log_channel:
                log_channel = await guild.create_text_channel(
                    name=logs_channel_name,
                    category=logs_category,
                    reason=f"Auto-created log channel for {map_info['name']} activity"
                )
                await log_channel.send(f"🗒️ Logs for **{map_info['name']}** initialized.")
                await asyncio.sleep(0.5)

            # =============================
            # 📂 Map Category
            # =============================
            category = discord.utils.get(guild.categories, name=category_name)
            if not category:
                category = await guild.create_category(
                    name=category_name,
                    reason=f"Auto-created for {map_info['name']} map setup"
                )
                await asyncio.sleep(0.5)

            # =============================
            # 🧭 Create or reuse flags channel
            # =============================
            flags_channel = discord.utils.get(guild.text_channels, name=flags_channel_name)
            if not flags_channel:
                flags_channel = await guild.create_text_channel(
                    name=flags_channel_name,
                    category=category,
                    reason=f"Auto-created for {map_info['name']} setup"
                )
                await flags_channel.send(f"📜 Flag ownership for **{map_info['name']}**.")

            # ✅ Sync permissions for organization
            await flags_channel.edit(sync_permissions=True)
            await log_channel.edit(sync_permissions=True)

            # =============================
            # 🏁 Initialize all flags
            # =============================
            for flag in FLAGS:
                await set_flag(guild_id, map_key, flag, "✅", None)
                await asyncio.sleep(0.05)  # prevent DB spam

            # =============================
            # 🖼️ Create embed + view
            # =============================
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

            # =============================
            # 💾 Save message + log IDs
            # =============================
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO flag_messages (guild_id, map, channel_id, message_id, log_channel_id)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (guild_id, map)
                    DO UPDATE SET
                        channel_id = EXCLUDED.channel_id,
                        message_id = EXCLUDED.message_id,
                        log_channel_id = EXCLUDED.log_channel_id;
                """, guild_id, map_key, str(flags_channel.id), str(msg.id), str(log_channel.id))

            # =============================
            # ✅ Success confirmation
            # =============================
            complete_embed = Embed(
                title="__SETUP COMPLETE__",
                description=(
                    f"✅ **{map_info['name']}** setup finished successfully.\n\n"
                    f"📂 **Map Category:** {category.name}\n"
                    f"🏁 **Flags:** {flags_channel.mention}\n"
                    f"🧭 **Logs:** {log_channel.mention}\n"
                    f"🪵 **Faction Logs:** {factions_log.mention}\n"
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

            # 🪵 Log setup to logs
            await log_action(
                guild,
                map_key,
                title="Map Setup Complete",
                description=(
                    f"✅ **{map_info['name']}** setup by {interaction.user.mention}.\n\n"
                    f"📂 Category: {category.name}\n"
                    f"🏁 Flags: {flags_channel.mention}\n"
                    f"🧭 Logs: {log_channel.mention}\n"
                    f"🪵 Faction Logs: {factions_log.mention}"
                ),
                color=0x2ECC71
            )

        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ Setup failed for **{map_info['name']}**:\n```{e}```"
            )
            await log_action(
                guild,
                map_key,
                title="Setup Failed",
                description=f"❌ Setup failed for **{map_info['name']}**:\n```{e}```",
                color=0xE74C3C
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(Setup(bot))
