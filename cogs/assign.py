import discord
from discord import app_commands
from discord.ext import commands
from cogs.utils import FLAGS, MAP_DATA, set_flag, get_all_flags, CUSTOM_EMOJIS, db_pool


class Assign(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 🪧 Universal embed builder with consistent DayZ Manager theme
    def make_embed(self, title, desc, color, icon="🪧 Assignment Update"):
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name=icon)
        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        embed.timestamp = discord.utils.utcnow()
        return embed

    # 🔍 Autocomplete for flags
    async def flag_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=flag, value=flag)
            for flag in FLAGS if current.lower() in flag.lower()
        ][:25]

    # 🧭 Update the live flag embed whenever a flag changes
    async def update_flag_message(self, guild, guild_id, map_key):
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
            embed.set_author(name="🚨 Live Flag Status Update")
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

    # 🎯 Core /assign command
    @app_commands.command(name="assign", description="Assign a flag to a role for a specific map.")
    @app_commands.describe(selected_map="Select the map", flag="Flag to assign", role="Role to assign to")
    @app_commands.choices(selected_map=[
        app_commands.Choice(name="Livonia", value="livonia"),
        app_commands.Choice(name="Chernarus", value="chernarus"),
        app_commands.Choice(name="Sakhal", value="sakhal"),
    ])
    @app_commands.autocomplete(flag=flag_autocomplete)
    async def assign(self, interaction: discord.Interaction, selected_map: app_commands.Choice[str], flag: str, role: discord.Role):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=self.make_embed(
                    "⚠️ ACCESS DENIED",
                    "You must be an **Administrator** to execute field assignments.",
                    0xED4245,
                    icon="🚫 Unauthorized Access"
                ),
                ephemeral=True
            )
            return

        guild_id = str(interaction.guild.id)
        map_key = selected_map.value

        # 🔍 Retrieve flag data
        existing_flags = await get_all_flags(guild_id, map_key)
        db_flags = {r["flag"]: r for r in existing_flags}

        # 🚫 Flag already owned
        if flag in db_flags and db_flags[flag]["status"] == "❌" and db_flags[flag]["role_id"]:
            current_owner = db_flags[flag]["role_id"]
            await interaction.response.send_message(
                embed=self.make_embed(
                    "🚫 FLAG ALREADY CLAIMED",
                    f"The **{flag}** flag on **{MAP_DATA[map_key]['name']}** is already occupied by <@&{current_owner}>.",
                    0xED4245,
                    icon="🚨 Assignment Rejected"
                ),
                ephemeral=True
            )
            return

        # 🚫 Role already holds another flag
        for record in existing_flags:
            if record["role_id"] == str(role.id):
                await interaction.response.send_message(
                    embed=self.make_embed(
                        "🚫 ROLE ALREADY ASSIGNED",
                        f"{role.mention} already controls the **{record['flag']}** flag on **{MAP_DATA[map_key]['name']}**.",
                        0xED4245,
                        icon="🚨 Conflict Detected"
                    ),
                    ephemeral=True
                )
                return

        # ✅ Assign new flag
        await set_flag(guild_id, map_key, flag, "❌", str(role.id))

        success_embed = self.make_embed(
            "✅ FLAG ASSIGNED SUCCESSFULLY",
            (
                f"**Flag:** {flag}\n"
                f"**Assigned To:** {role.mention}\n"
                f"**Map:** {MAP_DATA[map_key]['name']}\n\n"
                f"📡 Sector marked as **controlled**. Updating tactical display..."
            ),
            0x57F287,
            icon="🎯 Assignment Confirmed"
        )

        await interaction.response.send_message(embed=success_embed)

        # 🔁 Update live flag display
        await self.update_flag_message(interaction.guild, guild_id, map_key)


async def setup(bot):
    await bot.add_cog(Assign(bot))
