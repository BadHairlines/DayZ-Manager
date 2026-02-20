import discord
import asyncio
from discord.ext import commands
from discord import app_commands

# --- Predefined choices ---
TITLE_CHOICES = [
    app_commands.Choice(name="King Of The Hill", value="King Of The Hill"),
    app_commands.Choice(name="Fight Night", value="Fight Night"),
    app_commands.Choice(name="Battle Royale", value="Battle Royale"),
    app_commands.Choice(name="Swords vs Swords", value="Swords vs Swords")
]

KILL_REWARD_CHOICES = [
    app_commands.Choice(name="50,000", value="50,000"),
    app_commands.Choice(name="100,000", value="100,000"),
    app_commands.Choice(name="150,000", value="150,000"),
    app_commands.Choice(name="200,000", value="200,000")
]

LOADOUT_CHOICES = [
    app_commands.Choice(name="Provided", value="Provided"),
    app_commands.Choice(name="Not Provided", value="Not Provided")
]

SERVER_CHOICES = [
    app_commands.Choice(name="50x - Chernarus", value="50x - Chernarus"),
    app_commands.Choice(name="50x - Livonia", value="50x - Livonia")
]

class RoleDM(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Admin-only check
    def is_admin():
        async def predicate(interaction: discord.Interaction):
            return interaction.user.guild_permissions.administrator
        return app_commands.check(predicate)

    @app_commands.command(
        name="role_dm",
        description="DM everyone in a role with a rich embed (Admin Only)"
    )
    @app_commands.describe(
        role="The role to DM",
        server="Select the server",
        title="Event title",
        start_time="Start time (Unix timestamp)",
        description="Embed description for the main body",
        location="Event location",
        kill_reward="Reward per kill",
        loadouts="Loadouts provided",
        rules="Rules or warnings",
        image="Optional image file"
    )
    @is_admin()
    async def role_dm(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        title: str,
        start_time: str,
        description: str,
        location: str,
        kill_reward: str,
        loadouts: str,
        rules: str,
        server: str,
        image: discord.Attachment = None
    ):
        await interaction.response.defer(ephemeral=True, thinking=True)

        embed_color = discord.Color.from_rgb(255, 204, 0)
        embed_footer = "The Hive - 50x Servers"

        embed = discord.Embed(
            title=f"`{title}` - {start_time}",
            description=description,
            color=embed_color
        )

        embed.add_field(name="📍 Location", value=f"`{location}`", inline=True)
        embed.add_field(name="💰 Kill Reward", value=f"`{kill_reward}`", inline=True)
        embed.add_field(name="🔫 Loadouts", value=f"`{loadouts}`", inline=True)
        embed.add_field(name="⚠️ Rules", value=f"`{rules}`", inline=False)
        embed.add_field(name="🌍 Server", value=f"`{server}`", inline=False)
        embed.add_field(
            name="\u200b",
            value="[The Hive™ - DayZ Community](https://discord.com/invite/thehivedayz)",
            inline=False
        )

        if image:
            embed.set_image(url=image.url)

        embed.set_footer(text=embed_footer)

        members = [m for m in role.members if not m.bot]
        total = len(members)

        sent = 0
        failed = 0

        # Initial progress message
        progress_msg = await interaction.followup.send(
            content=f"📤 **Sending DMs…**\nProgress: **0 / {total}**",
            ephemeral=True
        )

        for index, member in enumerate(members, start=1):
            try:
                # Attempt DM with retry
                for attempt in range(3):
                    try:
                        await member.send(embed=embed)
                        sent += 1
                        break
                    except (discord.Forbidden, discord.HTTPException):
                        await asyncio.sleep(2 * (attempt + 1))  # exponential backoff
                        if attempt == 2:
                            failed += 1
            except Exception:
                failed += 1

            # Rate limit safe delay
            await asyncio.sleep(1.2)

            # Update progress every 25 users to reduce edit spam
            if index % 25 == 0 or index == total:
                try:
                    await progress_msg.edit(
                        content=(
                            f"📤 **Sending DMs…**\n"
                            f"Progress: **{index} / {total}**\n"
                            f"✅ Sent: {sent} | ❌ Failed: {failed}"
                        )
                    )
                except discord.HTTPException:
                    # Ignore edit errors; we'll do a final summary anyway
                    pass

        # Final summary
        try:
            await progress_msg.edit(
                content=(
                    f"✅ **Role DM Complete**\n\n"
                    f"📨 Sent: **{sent}**\n"
                    f"❌ Failed: **{failed}**\n"
                    f"👥 Total: **{total}**"
                )
            )
        except discord.HTTPException:
            pass

    # --- Autocomplete handlers ---
    @role_dm.autocomplete("title")
    async def title_autocomplete(self, interaction: discord.Interaction, current: str):
        return [c for c in TITLE_CHOICES if current.lower() in c.name.lower()]

    @role_dm.autocomplete("kill_reward")
    async def kill_reward_autocomplete(self, interaction: discord.Interaction, current: str):
        return [c for c in KILL_REWARD_CHOICES if current.lower() in c.name.lower()]

    @role_dm.autocomplete("loadouts")
    async def loadouts_autocomplete(self, interaction: discord.Interaction, current: str):
        return [c for c in LOADOUT_CHOICES if current.lower() in c.name.lower()]

    @role_dm.autocomplete("server")
    async def server_autocomplete(self, interaction: discord.Interaction, current: str):
        return [c for c in SERVER_CHOICES if current.lower() in c.name.lower()]

async def setup(bot: commands.Bot):
    await bot.add_cog(RoleDM(bot))
