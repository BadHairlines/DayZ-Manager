import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random
from datetime import datetime, timedelta
from cogs.utils import log_action


class ActivityCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.required_reactions = 4
        self.expiry_hours = 0.05  # ~3 minutes for testing
        self.emoji = "✅"

    # ==============================
    # 📦 Embed builder
    # ==============================
    def make_embed(self, name: str, role: discord.Role | None, color: int, progress=0, complete=False):
        mention_text = role.mention if role else f"**{name}**"

        if complete:
            desc = f"✅ **Activity Check Complete!** {mention_text} met the requirement!"
        else:
            desc = f"> At least **{self.required_reactions}** members of {mention_text} must click {self.emoji} below!"

        embed = discord.Embed(title="__**ACTIVITY CHECK**__", description=desc, color=color)
        if not complete:
            embed.add_field(name="Progress", value=f"✅ {progress}/{self.required_reactions} confirmed", inline=False)

        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        embed.timestamp = discord.utils.utcnow()
        return embed

    # ==============================
    # 🎯 Reaction tracking per channel
    # ==============================
    async def start_tracking(self, msg: discord.Message, role: discord.Role | None, color: int, results_dict: dict):
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
                        and (role is None or role in u.roles)
                    ),
                )

                confirmed_users.add(user.id)
                progress = len(confirmed_users)
                await msg.edit(embed=self.make_embed(msg.channel.name, role, color, progress))

                if progress >= self.required_reactions:
                    success = True
                    break

            except asyncio.TimeoutError:
                continue

        # ✅ Mark as complete or failed
        await msg.edit(embed=self.make_embed(msg.channel.name, role, color, len(confirmed_users), complete=success))

        # ✅ Store results (convert role.id to str for safety)
        results_dict[str(role.id) if role else msg.channel.name] = len(confirmed_users)

    # ==============================
    # 🧭 Detect faction role
    # ==============================
    async def detect_faction_role(self, channel: discord.TextChannel):
        """Detects which faction role owns the given channel based on permission overwrites."""
        for target, overwrite in channel.overwrites.items():
            if isinstance(target, discord.Role):
                if overwrite.view_channel is True and not target.is_default():
                    return target
        return None

    # ==============================
    # 🏆 Leaderboard builder
    # ==============================
    async def send_leaderboard(self, guild: discord.Guild, category: discord.CategoryChannel, results: dict):
        """Creates and posts a leaderboard summary to #activity-alerts."""
        alert_channel = discord.utils.get(guild.text_channels, name="activity-alerts")
        if not alert_channel:
            alert_channel = await guild.create_text_channel(
                "activity-alerts",
                reason="Created automatically for activity summaries"
            )

        # 🧮 Sort by most active first
        sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)

        embed = discord.Embed(
            title=f"🏆 Activity Check Results — {category.name}",
            description=f"📋 Activity check completed for **{len(results)} factions**.",
            color=0x00BFFF
        )

        for rank, (role_key, count) in enumerate(sorted_results, start=1):
            # Handle both str IDs and names
            role = None
            if isinstance(role_key, str) and role_key.isdigit():
                role = guild.get_role(int(role_key))
            elif isinstance(role_key, int):
                role = guild.get_role(role_key)

            name_display = role.mention if role else f"**{role_key}**"

            emoji = "✅" if count >= self.required_reactions else "❌"
            medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}."
            embed.add_field(
                name=f"{medal} {name_display}",
                value=f"{emoji} {count}/{self.required_reactions} members active",
                inline=False
            )

        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        embed.timestamp = discord.utils.utcnow()

        await alert_channel.send(embed=embed)
        print(f"📊 Posted leaderboard in #{alert_channel.name} for {guild.name}")

        # ⚠️ Ping failed factions
        failed_roles = []
        for k, v in results.items():
            role = None
            if isinstance(k, str) and k.isdigit():
                role = guild.get_role(int(k))
            elif isinstance(k, int):
                role = guild.get_role(k)
            if role and v < self.required_reactions:
                failed_roles.append(role)

        if failed_roles:
            await alert_channel.send(
                "⚠️ **The following factions failed their activity check:**\n" +
                " ".join(r.mention for r in failed_roles)
            )

    # ==============================
    # 💬 Slash Command
    # ==============================
    @app_commands.command(
        name="activity-check",
        description="Run activity checks for all faction channels in a category (map)."
    )
    @app_commands.describe(category="Select the category containing all faction channels.")
    async def activity_check(self, interaction: discord.Interaction, category: discord.CategoryChannel):
        """Posts and tracks activity checks for every channel in the given category."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admins only!", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)
        color = random.randint(0, 0xFFFFFF)
        sent_count = 0
        results = {}
        tasks = []

        for channel in category.text_channels:
            try:
                matched_role = await self.detect_faction_role(channel)
                embed = self.make_embed(channel.name, matched_role, color)
                content = matched_role.mention if matched_role else None
                msg = await channel.send(content=content, embed=embed)
                await msg.add_reaction(self.emoji)
                sent_count += 1

                # Run tracking concurrently
                task = asyncio.create_task(self.start_tracking(msg, matched_role, color, results))
                tasks.append(task)

                await asyncio.sleep(1)  # rate limit safety

            except discord.Forbidden:
                print(f"⚠️ No permission to send messages in {channel.name}.")
            except Exception as e:
                print(f"⚠️ Failed to post in {channel.name}: {e}")

        await interaction.followup.send(
            f"✅ Sent and tracking activity checks in **{sent_count}** channels under **{category.name}**!",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            category.name,
            title="Category Activity Check Started",
            description=f"📢 {interaction.user.mention} launched activity checks for **{category.name}**.",
            color=0x00BFFF
        )

        # 🕒 Wait for all tracking to finish before leaderboard
        if tasks:
            await asyncio.gather(*tasks)

        await self.send_leaderboard(interaction.guild, category, results)


async def setup(bot):
    await bot.add_cog(ActivityCheck(bot))
