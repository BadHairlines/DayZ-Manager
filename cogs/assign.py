import discord
from discord import app_commands
from discord.ext import commands
from cogs.helpers.base_cog import BaseCog
from cogs.helpers.decorators import admin_only, MAP_CHOICES
from cogs.utils import FLAGS, MAP_DATA, set_flag, get_all_flags, log_action, release_flag, create_flag_embed, db_pool


class FlagManageView(discord.ui.View):
    """Interactive management buttons for flag control."""

    def __init__(self, guild: discord.Guild, map_key: str, flag: str, bot: commands.Bot):
        super().__init__(timeout=180)
        self.guild = guild
        self.map_key = map_key
        self.flag = flag
        self.bot = bot

    async def update_flag_display(self):
        """Refresh the live flag embed after changes."""
        guild_id = str(self.guild.id)
        embed = await create_flag_embed(guild_id, self.map_key)

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT channel_id, message_id FROM flag_messages WHERE guild_id=$1 AND map=$2",
                guild_id, self.map_key
            )

        if not row:
            return

        channel = self.guild.get_channel(int(row["channel_id"]))
        if not channel:
            return

        try:
            msg = await channel.fetch_message(int(row["message_id"]))
            await msg.edit(embed=embed)
        except Exception as e:
            print(f"⚠️ Failed to update flag message: {e}")

    @discord.ui.button(label="🔁 Reassign", style=discord.ButtonStyle.primary)
    async def reassign_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Reassign flag to another role using a dropdown menu."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return

        options = [
            discord.SelectOption(label=role.name, value=str(role.id))
            for role in self.guild.roles
            if not role.is_default() and not role.is_bot_managed() and role.name != "@everyone"
        ][:25]

        select = discord.ui.Select(placeholder="Select new role...", options=options)

        async def select_callback(inter: discord.Interaction):
            new_role = self.guild.get_role(int(select.values[0]))
            guild_id = str(self.guild.id)

            # Prevent duplicate ownership
            existing_flags = await get_all_flags(guild_id, self.map_key)
            for record in existing_flags:
                if record["role_id"] == str(new_role.id):
                    await inter.response.send_message(
                        f"❌ {new_role.mention} already owns **{record['flag']}** on this map.",
                        ephemeral=True
                    )
                    return

            # Reassign in DB
            await set_flag(guild_id, self.map_key, self.flag, "❌", str(new_role.id))
            await self.update_flag_display()

            await log_action(
                self.guild,
                self.map_key,
                title="Flag Reassigned (UI)",
                description=f"🔁 **{self.flag}** → {new_role.mention}\nChanged by {inter.user.mention}",
                color=0x3498DB
            )

            await inter.response.send_message(
                f"🔁 **{self.flag}** successfully reassigned to {new_role.mention}.",
                ephemeral=True
            )

        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message("Select a new role:", view=view, ephemeral=True)

    @discord.ui.button(label="🏳 Release", style=discord.ButtonStyle.secondary)
    async def release_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Release the flag back to ✅ available."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return

        guild_id = str(self.guild.id)
        await release_flag(guild_id, self.map_key, self.flag)
        await self.update_flag_display()

        await log_action(
            self.guild,
            self.map_key,
            title="Flag Released (UI)",
            description=f"🏳️ **{self.flag}** released by {interaction.user.mention}",
            color=0x2ECC71
        )
        await interaction.response.send_message(f"✅ **{self.flag}** released successfully!", ephemeral=True)

    @discord.ui.button(label="❌ Close", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Remove the management view."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admins only.", ephemeral=True)
            return

        await interaction.message.delete()
        await interaction.response.send_message("🧹 Closed flag management panel.", ephemeral=True)


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

        # ✅ Send message with management view
        view = FlagManageView(guild, map_key, flag, self.bot)
        await interaction.response.send_message(embed=embed, view=view)

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
