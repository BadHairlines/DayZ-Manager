import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import asyncio
from cogs.utils import log_action  # ✅ add this import


# ✅ Official 25 DayZ faction/flag emojis only
FLAG_EMOJIS = {
    "APA": "https://i.postimg.cc/HW60bB1p/APA.png",
    "Altis": "https://i.postimg.cc/KjfMfcHq/Altis.png",
    "BabyDeer": "https://i.postimg.cc/Hk5QG3GC/BabyDeer.png",
    "Bear": "https://i.postimg.cc/qBxy4Qvs/Bear.png",
    "Bohemia": "https://i.postimg.cc/R0Bwvf9J/Bohemia.png",
    "BrainZ": "https://i.postimg.cc/X7NFJFrT/BrainZ.png",
    "Cannibals": "https://i.postimg.cc/MGmVHTKP/Cannibals.png",
    "CHEL": "https://i.postimg.cc/QCMj1XGJ/CHEL.png",
    "Chedaki": "https://i.postimg.cc/PxytCCcq/Chedaki.png",
    "CMC": "https://i.postimg.cc/3rL87DmS/CMC.png",
    "Crook": "https://i.postimg.cc/cLrn7SMh/Crook.png",
    "HunterZ": "https://i.postimg.cc/zXVJfXkJ/HunterZ.png",
    "NAPA": "https://i.postimg.cc/152yVhWD/NAPA.png",
    "NSahrani": "https://i.postimg.cc/0QqKqJgX/NSahrani.png",
    "Pirates": "https://i.postimg.cc/gJMhyTh3/Pirates.png",
    "Rex": "https://i.postimg.cc/ydXg6Ys1/Rex.png",
    "Refuge": "https://i.postimg.cc/NF5Hdk8S/Refuge.png",
    "Rooster": "https://i.postimg.cc/9Q9CG8SK/Rooster.png",
    "RSTA": "https://i.postimg.cc/pr4n45qT/RSTA.png",
    "Snake": "https://i.postimg.cc/66mRyFtX/Snake.png",
    "TEC": "https://i.postimg.cc/R0z9G1xF/TEC.png",
    "UEC": "https://i.postimg.cc/hjDnRSjR/UEC.png",
    "Wolf": "https://i.postimg.cc/vB0sQpgg/Wolf.png",
    "Zagorky": "https://i.postimg.cc/7P9Gp6KX/Zagorky.png",
    "Zenit": "https://i.postimg.cc/rszLzQxh/Zenit.png",
}


class SetupEmojis(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def make_embed(self, title: str, desc: str, color: int) -> discord.Embed:
        """Standard embed for setup notifications."""
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name="🚨 Emoji Setup Notification 🚨")
        embed.set_footer(
            text="DayZ Manager",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )
        embed.timestamp = discord.utils.utcnow()
        return embed

    @app_commands.command(
        name="setup-emojis",
        description="Add missing faction flag emojis (25 total) to the server."
    )
    async def setup_emojis(self, interaction: discord.Interaction):
        """Uploads only missing custom flag emojis to the guild."""
        guild = interaction.guild
        existing_names = {emoji.name for emoji in guild.emojis}

        # 🧠 Filter out ones that already exist
        missing_emojis = {name: url for name, url in FLAG_EMOJIS.items() if name not in existing_names}

        if not missing_emojis:
            await interaction.response.send_message(
                "✅ All 25 flag emojis already exist in this server!",
                ephemeral=True
            )
            # 🪵 Log all present
            await log_action(
                guild,
                "livonia",  # arbitrary map key for global logs
                title="Emoji Setup Check",
                description=f"✅ {interaction.user.mention} confirmed all 25 flag emojis already exist.",
                color=0x2ECC71
            )
            return

        await interaction.response.send_message(
            f"⚙️ Uploading **{len(missing_emojis)}** missing flag emojis... please wait ⏳",
            ephemeral=True
        )

        success, failed = 0, 0

        async with aiohttp.ClientSession() as session:
            for name, url in missing_emojis.items():
                try:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            failed += 1
                            continue
                        image_data = await resp.read()

                    await guild.create_custom_emoji(name=name, image=image_data)
                    success += 1
                    await asyncio.sleep(0.4)  # gentle rate limit buffer

                except discord.HTTPException as http_err:
                    print(f"⚠️ Discord error adding {name}: {http_err}")
                    failed += 1
                except Exception as e:
                    print(f"⚠️ Failed to add {name}: {e}")
                    failed += 1

        # ✅ Final summary
        embed = self.make_embed(
            "__FLAG EMOJI SETUP COMPLETE__",
            (
                f"✅ **{success} new emojis added successfully.**\n"
                f"⚪ **{25 - len(missing_emojis)} already existed.**\n"
                f"❌ **{failed} failed to upload.**"
            ),
            0x00FF00 if success > 0 else 0xFF0000
        )
        await interaction.followup.send(embed=embed)

        # 🪵 Log the results in embedded form
        await log_action(
            guild,
            "livonia",  # re-use a map key or handle via general log
            title="Emoji Setup Completed",
            description=(
                f"🪄 {interaction.user.mention} ran `/setup-emojis`.\n\n"
                f"✅ Added: **{success}**\n⚪ Skipped: **{25 - len(missing_emojis)}**\n❌ Failed: **{failed}**"
            ),
            color=0x3498DB if success > 0 else 0xE74C3C
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupEmojis(bot))
