import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import asyncio

# ✅ emoji name → image URL map
EMOJIS = {
    "Altis": "https://i.postimg.cc/KjfMfcHq/Altis.png",
    "APA": "https://i.postimg.cc/HW60bB1p/APA.png",
    "BabyDeer": "https://i.postimg.cc/Hk5QG3GC/BabyDeer.png",
    "Bear": "https://i.postimg.cc/qBxy4Qvs/Bear.png",
    "Bohemia": "https://i.postimg.cc/R0Bwvf9J/Bohemia.png",
    "BrainZ": "https://i.postimg.cc/X7NFJFrT/BrainZ.png",
    "Cannibals": "https://i.postimg.cc/MGmVHTKP/Cannibals.png",
    "CDF": "https://i.postimg.cc/HxdYWw6K/CDF.png",
    "Chedaki": "https://i.postimg.cc/PxytCCcq/Chedaki.png",
    "CHEL": "https://i.postimg.cc/QCMj1XGJ/CHEL.png",
    "Chernarus": "https://i.postimg.cc/pr1RBgPb/Chernarus.png",
    "CMC": "https://i.postimg.cc/3rL87DmS/CMC.png",
    "Crook": "https://i.postimg.cc/cLrn7SMh/Crook.png",
    "DayZ": "https://i.postimg.cc/HxW5ygrp/DayZ.png",
    "HunterZ": "https://i.postimg.cc/zXVJfXkJ/HunterZ.png",
    "Livonia": "https://i.postimg.cc/m2d9FDMh/Livonia.png",
    "LivoniaArmy": "https://i.postimg.cc/x1hbt462/Livonia-Army.png",
    "LivoniaPolice": "https://i.postimg.cc/Xv5BhkPy/Livonia-Police.png",
    "NSahrani": "https://i.postimg.cc/0QqKqJgX/NSahrani.png",
    "NAPA": "https://i.postimg.cc/152yVhWD/NAPA.png",
    "Pirates": "https://i.postimg.cc/gJMhyTh3/Pirates.png",
    "Refuge": "https://i.postimg.cc/NF5Hdk8S/Refuge.png",
    "RSTA": "https://i.postimg.cc/pr4n45qT/RSTA.png",
    "Rex": "https://i.postimg.cc/ydXg6Ys1/Rex.png",
    "Rooster": "https://i.postimg.cc/9Q9CG8SK/Rooster.png",
    "SSahrani": "https://i.postimg.cc/PJSCZ3C0/SSahrani.png",
    "Snake": "https://i.postimg.cc/66mRyFtX/Snake.png",
    "TEC": "https://i.postimg.cc/R0z9G1xF/TEC.png",
    "UEC": "https://i.postimg.cc/hjDnRSjR/UEC.png",
    "Wolf": "https://i.postimg.cc/vB0sQpgg/Wolf.png",
    "Zagorky": "https://i.postimg.cc/7P9Gp6KX/Zagorky.png",
    "Zenit": "https://i.postimg.cc/rszLzQxh/Zenit.png",
    "Black": "https://i.postimg.cc/Xv0Pm11J/Black.png",
    "Blue": "https://i.postimg.cc/Kvwwr8nt/Blue.png",
    "Green": "https://i.postimg.cc/7hQcRxj8/Green.png",
    "Orange": "https://i.postimg.cc/52zGPW3T/Orange.png",
    "Pink": "https://i.postimg.cc/qMzW33Ck/Pink.png",
    "Red": "https://i.postimg.cc/9MmnFRhH/Red.png",
    "Yellow": "https://i.postimg.cc/brCcj0D5/Yellow.png",
    "White": "https://i.postimg.cc/MTqhM314/White.png",
}


class SetupEmojis(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def make_embed(self, title: str, desc: str, color: int) -> discord.Embed:
        """Standard embed builder for emoji setup results."""
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
        description="Upload all flag and armband emojis to the server."
    )
    async def setup_emojis(self, interaction: discord.Interaction):
        """Uploads all custom flag/armband emojis to the guild."""
        await interaction.response.send_message(
            "⚙️ Uploading all flag emojis — please wait a few moments ⏳",
            ephemeral=True
        )

        guild = interaction.guild
        success, skipped, failed = 0, 0, 0
        total = len(EMOJIS)

        async with aiohttp.ClientSession() as session:
            for idx, (name, url) in enumerate(EMOJIS.items(), start=1):
                try:
                    # Skip if emoji already exists
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

                    # Respect Discord rate limits (50ms–500ms)
                    await asyncio.sleep(0.5)

                    # Periodic progress update in console
                    if idx % 10 == 0:
                        print(f"⏳ Uploaded {idx}/{total} emojis so far...")

                except discord.HTTPException as http_err:
                    # Handle Discord-side errors like quota exceeded
                    print(f"⚠️ Discord error on {name}: {http_err}")
                    failed += 1
                except Exception as e:
                    print(f"⚠️ Failed to upload {name}: {e}")
                    failed += 1

        # 🟢 Summary
        embed = self.make_embed(
            "__EMOJI SETUP COMPLETE__",
            (
                f"✅ **{success} emojis uploaded successfully.**\n"
                f"⚪ **{skipped} already existed.**\n"
                f"❌ **{failed} failed due to errors or quota limits.**"
            ),
            0x00FF00 if success > 0 else 0xFF0000
        )

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupEmojis(bot))
