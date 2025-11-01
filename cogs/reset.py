import discord
from discord import app_commands
from discord.ext import commands
from cogs.utils import reset_map_flags, MAP_DATA, FLAGS, get_all_flags, CUSTOM_EMOJIS, db_pool
import asyncpg
import asyncio

class Reset(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def make_embed(self, title, desc, color):
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name="🧹 Reset Notification 🧹")
        embed.set_footer(
            text="DayZ Manager",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )
        return embed

    async def update_flag_message(self, guild, guild_id, map_key):
        """Refresh the live flag message embed after reset."""
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
            records = await get_all_flags(guild_id, map_key)
            db_flags = {r["flag"]: r for r in records}

            embed = discord.Embed(
                title=f"**———⛳️ {MAP_DATA[map_key]['name'].upper()} FLAGS ⛳️———**",
                color=0x86DC3D
            )
            embed.set_author(name="🚨 Flags Notification 🚨")
            embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")

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

            await msg.edit(embed=embed)
        except Exception as e:
            print(f"⚠️ Failed to update flag message after reset: {e}")

    @app_commands.command(name="reset", description="Reset all flags for a selected map back to ✅.")
    @app_commands.describe(selected_map="Select the map to reset (Livonia, Chernarus, Sakhal)")
    @app_commands.choices(selected_map=[
        app_commands.Choice(name="Livonia", value="livonia"),
        app_commands.Choice(name="Chernarus", value="chernarus"),
        app_commands.Choice(name="Sakhal", value="sakhal"),
    ])
    async def reset(self, interaction: discord.Interaction, selected_map: app_commands.Choice[str]):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ This command is for admins ONLY!", ephemeral=True)
            return

        guild = interaction.guild
        guild_id = str(guild.id)
        map_key = selected_map.value
        map_info = MAP_DATA[map_key]

        # 🟡 Step 1: Send temporary loading message like /setup
        await interaction.response.send_message(
            f"🧹 Resetting **{map_info['name']}** flags... please wait ⏳",
            ephemeral=True
        )

        try:
            # 🟢 Step 2: Reset all flags in DB
            await reset_map_flags(guild_id, map_key)
            await asyncio.sleep(1)  # tiny delay for realism

            # 🟢 Step 3: Update the flag display embed
            await self.update_flag_message(guild, guild_id, map_key)

            # 🟢 Step 4: Create final success embed
            embed = discord.Embed(
                title="__RESET COMPLETE__",
                description=(
                    f"✅ **{map_info['name']}** flags successfully reset.\n\n"
                    f"All flags are now marked as ✅ and the live display has been refreshed."
                ),
                color=0x00FF00
            )
            embed.set_image(url=map_info["image"])
            embed.set_author(name="🧹 Reset Notification 🧹")
            embed.set_footer(
                text="DayZ Manager",
                icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
            )
            embed.timestamp = discord.utils.utcnow()

            # 🟢 Step 5: Edit original message with completion embed
            await interaction.edit_original_response(content=None, embed=embed)

        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ Reset failed for **{map_info['name']}**:\n```{e}```"
            )

async def setup(bot):
    await bot.add_cog(Reset(bot))
