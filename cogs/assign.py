import discord
from discord import app_commands
from discord.ext import commands
from cogs.utils import FLAGS, MAP_DATA, set_flag, get_all_flags, CUSTOM_EMOJIS, db_pool

class Assign(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def make_embed(self, title, desc, color):
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name="🪧 Assign Notification 🪧")
        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        return embed

    async def update_flag_message(self, guild, guild_id, map_key):
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2", guild_id, map_key)
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
            print(f"⚠️ Failed to update flag message: {e}")

    @app_commands.command(name="assign", description="Assign a flag to a role for a specific map.")
    @app_commands.describe(selected_map="Select the map (Livonia, Chernarus, Sakhal)", flag="Flag to assign", role="Role to assign to")
    @app_commands.choices(selected_map=[
        app_commands.Choice(name="Livonia", value="livonia"),
        app_commands.Choice(name="Chernarus", value="chernarus"),
        app_commands.Choice(name="Sakhal", value="sakhal"),
    ])
    async def assign(self, interaction: discord.Interaction, selected_map: app_commands.Choice[str], flag: str, role: discord.Role):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You must be an administrator to use this command.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        map_key = selected_map.value
        await set_flag(guild_id, map_key, flag, "❌", str(role.id))

        embed = self.make_embed(
            "**ASSIGNED**",
            f"The **{flag} Flag** has been marked as ❌ on **{MAP_DATA[map_key]['name']}** and assigned to {role.mention}.",
            0x86DC3D
        )
        await interaction.response.send_message(embed=embed)

        await self.update_flag_message(interaction.guild, guild_id, map_key)

async def setup(bot):
    await bot.add_cog(Assign(bot))
