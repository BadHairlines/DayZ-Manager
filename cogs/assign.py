import discord
from discord import app_commands
from discord.ext import commands
from cogs.helpers.base_cog import BaseCog
from cogs.helpers.decorators import admin_only, MAP_CHOICES
from cogs.utils import FLAGS, MAP_DATA, set_flag, get_all_flags, log_action


class Assign(commands.Cog, BaseCog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def flag_autocomplete(self, interaction: discord.Interaction, current: str):
        """Autocomplete for flag names."""
        return [
            app_commands.Choice(name=flag, value=flag)
            for flag in FLAGS if current.lower() in flag.lower()
        ][:25]

    @app_commands.command(name="assign", description="Assign a flag to a role for a specific map.")
    @app_commands.choices(selected_map=MAP_CHOICES)
    @app_commands.autocomplete(flag=flag_autocomplete)
    @admin_only()
    async def assign(
        self,
        interaction: discord.Interaction,
        selected_map: app_commands.Choice[str],
        flag: str,
        role: discord.Role
    ):
        """Assigns a flag to a specific role."""
        guild = interaction.guild
        guild_id = str(guild.id)
        map_key = selected_map.value
        map_name = MAP_DATA[map_key]["name"]

        # ✅ Fetch all flags for this map
        existing_flags = await get_all_flags(guild_id, map_key)
        db_flags = {r["flag"]: r for r in existing_flags}

        # 🚫 Check if this flag is already taken
        if flag in db_flags and db_flags[flag]["status"] == "❌" and db_flags[flag]["role_id"]:
            current_owner = db_flags[flag]["role_id"]
            embed = self.make_embed(
                "**FLAG ALREADY CLAIMED**",
                f"❌ The **{flag}** flag on **{map_name}** is already assigned to <@&{current_owner}>.",
                0xE74C3C,
                "🪧",
                "Assign Notification"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            await log_action(
                guild,
                map_key,
                title="Assign Attempt Failed",
                description=f"⚠️ {interaction.user.mention} tried to assign **{flag}**, "
                            f"but it’s already owned by <@&{current_owner}>.",
                color=0xE74C3C
            )
            return

        # 🚫 Check if this role already owns another flag
        for record in existing_flags:
            if record["role_id"] == str(role.id):
                embed = self.make_embed(
                    "**ROLE ALREADY HAS A FLAG**",
                    f"{role.mention} already owns the **{record['flag']}** flag on **{map_name}**.",
                    0xF1C40F,
                    "🪧",
                    "Assign Notification"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                await log_action(
                    guild,
                    map_key,
                    title="Duplicate Flag Attempt",
                    description=f"⚠️ {interaction.user.mention} tried to assign another flag "
                                f"to {role.mention} (already owns **{record['flag']}**).",
                    color=0xF1C40F
                )
                return

        # ✅ Assign the flag
        await set_flag(guild_id, map_key, flag, "❌", str(role.id))

        # ✅ Success embed
        embed = self.make_embed(
            "**FLAG ASSIGNED**",
            f"✅ The **{flag}** flag has been marked as ❌ and assigned to {role.mention} on **{map_name}**.",
            0x2ECC71,
            "🪧",
            "Assign Notification"
        )
        await interaction.response.send_message(embed=embed)

        # 🔁 Update live display
        await self.update_flag_message(guild, guild_id, map_key)

        # 🪵 Structured log for assignment
        await log_action(
            guild,
            map_key,
            title="Flag Assigned",
            description=f"🪧 **{flag}** → {role.mention}\nAssigned by {interaction.user.mention}",
            color=0x2ECC71
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Assign(bot))
