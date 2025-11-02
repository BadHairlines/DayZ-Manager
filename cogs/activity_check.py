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
        self.expiry_hours = 0.05  # ⏱️ ~3 minutes for testing (change to 12 later)
        self.emoji = "✅"

    def make_embed(self, name: str, role: discord.Role | None, color: int, progress=0, complete=False):
        """Creates the activity check embed."""
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

    async def start_tracking(self, msg: discord.Message, role: discord.Role | None, color: int, results_dict: dict):
        """Tracks reactions for a single activity check message."""
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

        # ✅ Mark as complete
        await msg.edit(embed=self.make_embed(msg.channel.name, role, color, len(confirmed_users), complete=success))
        results_dict[msg.channel.name] = len(confirmed_users)

    async def send_leaderboard(self, guild: discord.Guild, category: discord.CategoryChannel, results: dict):
        """Creates and posts a leaderboard summary to #activity-alerts."""
        # Find or create the alerts channel
        alert_channel = discord.utils.get(guild.text_channels, name="activity-alerts")
        if not alert_channel:
            alert_channel = await guild.create_text_channel(
                "activity-alerts",
                reason="Created automatically for activity summaries"
            )

        # Sort results (highest reactions first)
        sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)

        embed = discord.Embed(
            title=f"🏆 Activity Check Results — {category.name}",
            description=f"Activity check completed for **{len(results)} factions**.",
            color=0x00BFFF
        )

        for rank, (name, count) in enumerate(sorted_results, start=1):
            emoji = "✅" if count >= self.required_reactions else "❌"
            embed.add_field(
                name=f"{rank}. {name}",
                value=f"{emoji} {count}/{self.required_reactions} members active",
                inline=False
            )

        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        embed.timestamp = discord.utils.utcnow()

        await alert_channel.send(embed=embed)
        print(f"📊 Posted leaderboard in #{alert_channel.name} for {guild.name}")

    @app_commands.command(name="activity-check", description="Run activity checks for all faction channels in a category (map).")
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

        # Send checks to all faction channels
        for channel in category.text_channels:
            try:
                matched_role = discord.utils.find(
                    lambda r: r.name.lower().replace(" ", "-") in channel.name.lower(),
                    interaction.guild.roles
                )

                embed = self.make_embed(channel.name, matched_role, color)
                content = matched_role.mention if matched_role else None
                msg = await channel.send(content=content, embed=embed)
                await msg.add_reaction(self.emoji)
                sent_count += 1

                # Track each check concurrently
                self.bot.loop.create_task(self.start_tracking(msg, matched_role, color, results))
                await asyncio.sleep(1)

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

        # Wait for all checks to finish (shorter timer for testing)
        await asyncio.sleep(self.expiry_hours * 3600 + 10)

        # Post leaderboard summary
        await self.send_leaderboard(interaction.guild, category, results)


async def setup(bot):
    await bot.add_cog(ActivityCheck(bot))
