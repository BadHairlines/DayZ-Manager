import discord
from discord import app_commands
from discord.ext import commands
from cogs.utils import (
    FLAGS, MAP_DATA, get_all_flags, set_flag,
    db_pool, create_flag_embed, log_action
)


class Reassign(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def make_embed(self, title: str, desc: str, color: int) -> discord.Embed:
        """Helper to make consistent embeds."""
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name="🔁 Reassign Notification 🔁")
        embed.set_footer(
            text="DayZ Manager",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )
        return embed

    async def flag_autocomplete(self, interaction: discord.Interaction, current: str):
        """Autocomplete flag names."""
        return [
            app_commands.Choice(name=flag, value=flag)
            for flag in FLAGS if current.lower() in flag.lower()
        ][:25]

    async def update_flag_message(self, guild: discord.Guild, guild_id: str, map_key: str):
        """Refresh the live flag message embed after reassign."""
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
            embed = await create_flag_embed(guild_id, map_key)
            await msg.edit(embed=embed)
        except Exception as e:
            print(f"⚠️ Failed to update flag message after reassign: {e}")

    @app_commands.command(name="reassign", description="Move a flag from one role to another for a specific map.")
    @app_commands.describe(selected_map="Select the map", flag="Flag to reassign", new_role="New role to assign to")
    @app_commands.choices(selected_map=[
        app_commands.Choice(name="Livonia", value="livonia"),
        app_commands.Choice(name="Chernarus", value="chernarus"),
        app_commands.Choice(name="Sakhal", value="sakhal"),
    ])
    @app_commands.autocomplete(flag=flag_autocomplete)
    async def reassign(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str],
        flag: str,
        new_role: discord.Role
    ):
        """Transfers a flag from one role to another."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You must be an administrator to use this command.",
                ephemeral=True
            )
            return

        guild = interaction.guild
        guild_id = str(guild.id)
        map_key = selected_map.value
        map_name = MAP_DATA[map_key]["name"]

        # ✅ Fetch all current flags
        existing_flags = await get_all_flags(guild_id, map_key)
        db_flags = {r["flag"]: r for r in existing_flags}

        # 🚫 Check if this flag exists
        if flag not in db_flags:
            await interaction.response.send_message(
                f"❌ The **{flag}** flag doesn’t exist or hasn’t been initialized yet. Run `/setup` first.",
                ephemeral=True
            )
            return

        current_owner = db_flags[flag]["role_id"]
        if not current_owner:
            await interaction.response.send_message(
                f"⚠️ The **{flag}** flag isn’t currently assigned to any role.",
                ephemeral=True
            )
            return

        # 🚫 Prevent assigning to same role
        if str(new_role.id) == current_owner:
            await interaction.response.send_message(
                f"⚠️ The **{flag}** flag is already assigned to {new_role.mention}.",
                ephemeral=True
            )
            return

        # 🚫 Check if new role already owns another flag
        for record in existing_flags:
            if record["role_id"] == str(new_role.id):
                await interaction.response.send_message(
                    f"❌ {new_role.mention} already owns the **{record['flag']}** flag on **{map_name}**.",
                    ephemeral=True
                )
                return

        # ✅ Reassign in DB
        await set_flag(guild_id, map_key, flag, "❌", str(new_role.id))

        # ✅ Build confirmation embed
        embed = self.make_embed(
            "**FLAG REASSIGNED**",
            f"🔁 The **{flag}** flag has been transferred from <@&{current_owner}> "
            f"to {new_role.mention} on **{map_name}**.",
            0x3498DB
        )
        await interaction.response.send_message(embed=embed)

        # 🔁 Update live display
        await self.update_flag_message(guild, guild_id, map_key)

        # 🪵 Structured log for reassign
        await log_action(
            guild,
            map_key,
            title="Flag Reassigned",
            description=f"🔁 **{flag}** moved from <@&{current_owner}> → {new_role.mention}\n"
                        f"👤 Changed by {interaction.user.mention} on **{map_name}**.",
            color=0x3498DB
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Reassign(bot))
