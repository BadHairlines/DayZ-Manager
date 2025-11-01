import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import asyncio

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
        embed.set_author(name="🚨 Setup Notification 🚨")
        embed.set_footer(
            text="DayZ Manager",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )
        embed.timestamp = discord.utils.utcnow()
        return embed

    @app_commands.command(
        name="setup-emojis",
        description="Add all 25 faction flag emojis to the server."
    )
    async def setup_emojis(self, interaction: discord.Interaction):
        """Uploads the 25 official DayZ flag emojis to the guild."""
        await interaction.response.send_message(
            "⚙️ Uploading 25 flag emojis... please wait ⏳",
            ephemeral=True
        )

        guild = interaction.guild
        success, skipped, failed = 0, 0, 0
        total = len(FLAG_EMOJIS)

        async with aiohttp.ClientSession() as session:
            for name, url in FLAG_EMOJIS.items():
                try:
                    # Skip existing emojis
                    if discord.utils.get(guild.emojis, name=name):
                        skipped += 1
                        continue

                    async with session.get(url) as resp:
                        if resp.status != 200:
                            failed += 1
                            continue
                        image_data = await resp.read()

                    await guild.create_custom_emoji(name=name, image=image_data)
                    success += 1
                    await asyncio.sleep(0.4)  # brief delay to respect rate limits

                except discord.HTTPException as http_err:
                    print(f"⚠️ Discord error adding {name}: {http_err}")
                    failed += 1
                except Exception as e:
                    print(f"⚠️ Failed to add {name}: {e}")
                    failed += 1

        # ✅ Completion summary
        embed = self.make_embed(
            "__FLAG EMOJIS SETUP COMPLETE__",
            (
                f"✅ **{success} emojis added successfully.**\n"
                f"⚪ **{skipped} already existed.**\n"
                f"❌ **{failed} failed (invalid or quota limit).**"
            ),
            0x00FF00 if success > 0 else 0xFF0000
        )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupEmojis(bot))
