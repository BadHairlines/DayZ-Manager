import discord
import asyncio
from discord.ext import commands
from discord import app_commands

class RoleDM(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def is_admin():
        async def predicate(interaction: discord.Interaction):
            return interaction.user.guild_permissions.administrator
        return app_commands.check(predicate)

    @app_commands.command(
        name="role_dm",
        description="DM everyone in a role with a rich embed (Admin Only)"
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
        await interaction.edit_original_response(
            content=f"📤 **Sending DMs…**\nProgress: **0 / {total}**"
        )

        for index, member in enumerate(members, start=1):
            try:
                await member.send(embed=embed)
                sent += 1
                await asyncio.sleep(1.1)
            except discord.Forbidden:
                failed += 1
            except discord.HTTPException:
                failed += 1
                await asyncio.sleep(3)

            # 🔄 Update progress every 10 users OR at the end
            if index % 10 == 0 or index == total:
                await interaction.edit_original_response(
                    content=(
                        f"📤 **Sending DMs…**\n"
                        f"Progress: **{index} / {total}**\n"
                        f"✅ Sent: {sent} | ❌ Failed: {failed}"
                    )
                )

        # Final result
        await interaction.edit_original_response(
            content=(
                f"✅ **Role DM Complete**\n\n"
                f"📨 Sent: **{sent}**\n"
                f"❌ Failed: **{failed}**\n"
                f"👥 Total: **{total}**"
            )
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(RoleDM(bot))
