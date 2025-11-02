import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random
from datetime import datetime, timedelta

from cogs.utils import log_action, get_all_flags, release_flag, db_pool

class ActivityCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.required_reactions = 4         # ✅ minimum number of members
        self.expiry_hours = 12               # 🕒 auto-expire time
        self.emoji = "✅"

    def make_embed(self, role, color, progress=0, complete=False, failed=False):
        """Builds an updated activity check embed."""
        description = (
            f"> At least **{self.required_reactions}** members of {role.mention} must click {self.emoji} below!"
        )

        if complete:
            description = f"✅ **Activity Check Complete!** {role.mention} met the requirement!"
        elif failed:
            description = f"❌ **Activity Check Failed!** Not enough members of {role.mention} responded."

        embed = discord.Embed(
            title="__**ACTIVITY CHECK**__",
            description=description,
            color=color
        )

        if not complete and not failed:
            embed.add_field(
                name="Progress",
                value=f"✅ {progress}/{self.required_reactions} confirmed",
                inline=False
            )

        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        embed.timestamp = discord.utils.utcnow()
        return embed

    @app_commands.command(name="activity-check", description="Start an activity check for a faction or role.")
    @app_commands.describe(role="Select the faction or role to ping for activity")
    async def activity_check(self, interaction: discord.Interaction, role: discord.Role):
        """Launches an automated faction activity check."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admins only!", ephemeral=True)
            return

        color = random.randint(0, 0xFFFFFF)
        embed = self.make_embed(role, color)

        # Send initial message
        msg = await interaction.channel.send(content=role.mention, embed=embed)
        await msg.add_reaction(self.emoji)
        await interaction.response.send_message(f"✅ Activity check started for {role.mention}!", ephemeral=True)

        # Store who reacted
        confirmed_users = set()

        # Wait for reactions up to expiry time
        end_time = datetime.utcnow() + timedelta(hours=self.expiry_hours)
        success = False

        while datetime.utcnow() < end_time:
            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add",
                    timeout=60,
                    check=lambda r, u: (
                        r.message.id == msg.id
                        and str(r.emoji) == self.emoji
                        and not u.bot
                        and role in u.roles
                    ),
                )

                confirmed_users.add(user.id)
                progress = len(confirmed_users)

                # Update embed with progress
                updated_embed = self.make_embed(role, color, progress)
                await msg.edit(embed=updated_embed)

                if progress >= self.required_reactions:
                    success = True
                    break

            except asyncio.TimeoutError:
                # no reactions within 60s → continue loop
                continue

        guild = interaction.guild
        guild_id = str(guild.id)

        if success:
            # ✅ Mark faction as active
            final_embed = self.make_embed(role, color, complete=True)
            await msg.edit(embed=final_embed)
            await log_action(
                guild,
                "N/A",
                title="Activity Check Passed",
                description=f"✅ {role.mention} passed activity check with {len(confirmed_users)} members.",
                color=0x2ECC71
            )

            # 🕒 Update last_active in DB
            async with db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE flags SET last_active=NOW() WHERE guild_id=$1 AND role_id=$2",
                    guild_id, str(role.id)
                )

        else:
            # ❌ Mark as failed
            final_embed = self.make_embed(role, color, failed=True)
            await msg.edit(embed=final_embed)
            await log_action(
                guild,
                "N/A",
                title="Activity Check Failed",
                description=f"❌ {role.mention} failed to meet the activity requirement.",
                color=0xE74C3C
            )

            # 🔁 Find and release their flag automatically
            existing_flags = await get_all_flags(guild_id, "livonia")  # adjust if multi-map
            for record in existing_flags:
                if record["role_id"] == str(role.id):
                    await release_flag(guild_id, record["map"], record["flag"])
                    await log_action(
                        guild,
                        record["map"],
                        title="Flag Auto-Released (Inactive)",
                        description=f"🏳️ {record['flag']} automatically released from {role.mention} due to failed activity check.",
                        color=0xE67E22
                    )
                    break


async def setup(bot):
    await bot.add_cog(ActivityCheck(bot))
