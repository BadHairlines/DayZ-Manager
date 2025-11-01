import discord
from discord import app_commands, Interaction, Embed
from discord.ext import commands
from cogs.utils import FLAGS, MAP_DATA, CUSTOM_EMOJIS, set_flag, get_all_flags, db_pool
import asyncio


class Setup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def create_flag_embed(self, guild_id, map_key):
        records = await get_all_flags(guild_id, map_key)
        db_flags = {r["flag"]: r for r in records}

        embed = Embed(
            title=f"**———⛳️ {MAP_DATA[map_key]['name'].upper()} FLAGS ⛳️———**",
            color=0x86DC3D
        )
        embed.set_author(name="🚨 Flags Notification 🚨")
        embed.set_footer(
            text="DayZ Manager",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )
        embed.timestamp = discord.utils.utcnow()

        lines = []
        for flag in FLAGS:
            data = db_flags.get(flag)
            status = data["status"] if data else "✅"
            role_id = data["role_id"] if data and data["role_id"] else None
            emoji = CUSTOM_EMOJIS.get(flag, "")
            if not emoji.startswith("<:"):
                emoji = ""
            display_value = "✅" if status == "✅" else (f"<@&{role_id}>" if role_id else "❌")
            lines.append(f"{emoji} **• {flag}**: {display_value}")

        embed.description = "\n".join(lines)
        return embed

    @app_commands.command(name="setup", description="Setup or refresh a map and initialize all flags in the database.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(selected_map="Select the map to setup (Livonia, Chernarus, Sakhal)")
    @app_commands.choices(selected_map=[
        app_commands.Choice(name="Livonia", value="livonia"),
        app_commands.Choice(name="Chernarus", value="chernarus"),
        app_commands.Choice(name="Sakhal", value="sakhal"),
    ])
    async def setup(self, interaction: Interaction, selected_map: app_commands.Choice[str]):
        guild = interaction.guild
        guild_id = str(guild.id)
        map_key = selected_map.value
        map_info = MAP_DATA[map_key]
        channel_name = f"flags-{map_key}"

        await interaction.response.send_message(
            f"⚙️ Setting up **{map_info['name']}** flags... please wait ⏳",
            ephemeral=True
        )

        try:
            async with db_pool.acquire() as conn:
                # ✅ Properly closed triple quotes here
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS flag_messages (
                        guild_id TEXT NOT NULL,
                        map TEXT NOT NULL,
                        channel_id TEXT NOT NULL,
                        message_id TEXT NOT NULL,
                        PRIMARY KEY (guild_id, map)
                    );
                """)
                row = await conn.fetchrow(
                    "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                    guild_id, map_key
                )

            # ✅ Reuse or create the channel
            existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
            if existing_channel:
                setup_channel = existing_channel
            else:
                setup_channel = await guild.create_text_channel(
                    name=channel_name,
                    reason=f"Auto-created for {map_info['name']} setup"
                )
                await setup_channel.send(
                    f"📜 This channel displays flag ownership for **{map_info['name']}**."
                )

            # ✅ Initialize flags
            for flag in FLAGS:
                await set_flag(guild_id, map_key, flag, "✅", None)
                await asyncio.sleep(0.05)

            embed = await self.create_flag_embed(guild_id, map_key)

            # ✅ Update or recreate message
            if row:
                try:
                    channel = guild.get_channel(int(row["channel_id"]))
                    msg = await channel.fetch_message(int(row["message_id"]))
                    await msg.edit(embed=embed)
                    msg_id = msg.id
                except Exception:
                    msg = await setup_channel.send(embed=embed)
                    msg_id = msg.id
            else:
                msg = await setup_channel.send(embed=embed)
                msg_id = msg.id

            # ✅ Store message info
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO flag_messages (guild_id, map, channel_id, message_id)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (guild_id, map)
                    DO UPDATE SET channel_id = EXCLUDED.channel_id, message_id = EXCLUDED.message_id;
                """, guild_id, map_key, str(setup_channel.id), str(msg_id))

            # ✅ Success response
            complete_embed = Embed(
                title="__SETUP COMPLETE__",
                description=(
                    f"✅ **{map_info['name']}** setup finished successfully.\n\n"
                    f"📁 Flags channel: {setup_channel.mention}\n"
                    f"🧭 Live flag message refreshed automatically."
                ),
                color=0x00FF00
            )
            complete_embed.set_image(url=map_info["image"])
            complete_embed.set_author(name="🚨 Setup Notification 🚨")
            complete_embed.set_footer(
                text="DayZ Manager",
                icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
            )
            complete_embed.timestamp = discord.utils.utcnow()

            await interaction.edit_original_response(content=None, embed=complete_embed)

        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ Setup failed for **{map_info['name']}**:\n```{e}```"
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Setup(bot))
