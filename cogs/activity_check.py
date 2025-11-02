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
        self.required_reactions = 4
        self.expiry_hours = 12
        self.emoji = "✅"

    def make_embed(self, role, color, progress=0, complete=False, failed=False):
        desc = f"> At least **{self.required_reactions}** members of {role.mention} must click {self.emoji} below!"

        if complete:
            desc = f"✅ **Activity Check Complete!** {role.mention} met the requirement!"
        elif failed:
            desc = f"❌ **Activity Check Failed!** Not enough members of {role.mention} responded."

        embed = discord.Embed(title="__**ACTIVITY CHECK**__", description=desc, color=color)
        if not complete and not failed:
            embed.add_field(name="Progress", value=f"✅ {progress}/{self.required_reactions} confirmed", inline=False)

        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        embed.timestamp = discord.utils.utcnow()
        return embed

    @app_commands.command(name="activity-check", description="Start an activity check for a faction or all channels in a category.")
    @app_commands.describe(
        role="Faction or role to ping (ignored if you use 'category')",
        category="Run activity checks in every text channel inside this category"
    )
    async def activity_check(self, interaction: discord.Interaction, role: discord.Role | None = None, category: discord.CategoryChannel | None = None):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admins only!", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)
        color = random.randint(0, 0xFFFFFF)

        # ===============================
        # 🌍 MULTI-CHANNEL MODE (Category)
        # ===============================
        if category:
            sent_count = 0
            for channel in category.text_channels:
                try:
                    # Try to match the faction role to the channel name
                    matched_role = None
                    for r in interaction.guild.roles:
                        if r.name.lower().replace(" ", "-") in channel.name.lower():
                            matched_role = r
                            break

                    if not matched_role:
                        continue  # skip if no faction role matches

                    embed = self.make_embed(matched_role, color)
                    msg = await channel.send(content=matched_role.mention, embed=embed)
                    await msg.add_reaction(self.emoji)
                    sent_count += 1
                    await asyncio.sleep(1)

                except Exception as e:
                    print(f"⚠️ Failed to post in {channel.name}: {e}")

            await interaction.followup.send(f"✅ Sent activity checks to **{sent_count}** channels in {category.name}!", ephemeral=True)
            return

        # ==========================
        # 🎯 SINGLE ROLE MODE
        # ==========================
        if not role:
            await interaction.followup.send("❌ You must provide either a `role` or a `category`.", ephemeral=True)
            return

        embed = self.make_embed(role, color)
        msg = await interaction.channel.send(content=role.mention, embed=embed)
        await msg.add_reaction(self.emoji)
        await interaction.followup.send(f"✅ Activity check started for {role.mention}!", ephemeral=True)

        # Track reactions
        confirmed_users = set()
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
                await msg.edit(embed=self.make_embed(role, color, progress))
                if progress >= self.required_reactions:
                    success = True
                    break
            except asyncio.TimeoutError:
                continue

        guild = interaction.guild
        guild_id = str(guild.id)

        # ✅ Success
        if success:
            await msg.edit(embed=self.make_embed(role, color, complete=True))
            await log_action(
                guild,
                "N/A",
                title="Activity Check Passed",
                description=f"✅ {role.mention} passed activity check with {len(confirmed_users)} members.",
                color=0x2ECC71
            )

            async with db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE flags SET last_active=NOW() WHERE guild_id=$1 AND role_id=$2",
                    guild_id, str(role.id)
                )
        else:
            # ❌ Failed
            await msg.edit(embed=self.make_embed(role, color, failed=True))
            await log_action(
                guild,
                "N/A",
                title="Activity Check Failed",
                description=f"❌ {role.mention} failed to meet the activity requirement.",
                color=0xE74C3C
            )

            existing_flags = await get_all_flags(guild_id, "livonia")  # or auto-detect later
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
