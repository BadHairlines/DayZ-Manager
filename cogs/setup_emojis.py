import discord
from discord import app_commands
from discord.ext import commands
from cogs.utils import server_vars, save_data
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
    def __init__(self, bot):
        self.bot = bot

    def make_embed(self, title, desc, color):
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name="🚨 Setup Notification 🚨")
        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        embed.timestamp = discord.utils.utcnow()
        return embed

    @app_commands.command(name="setup-emojis", description="Add all flag and armband emojis to the server.")
    async def setup_emojis(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        guild_data = server_vars.setdefault(guild_id, {})

        # ✅ Prevent re-adding if already done
        if guild_data.get("emojisAdded") == "✅":
            embed = self.make_embed(
                "❌ __Emojis Already Set Up__ ❌",
                "> If you're missing any, please reach out to the **DayZ Manager Support Team** for assistance.",
                0xFF0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.send_message("⚙️ Adding all flag emojis... This may take a few seconds.", ephemeral=True)
        success = 0
        fail = 0

        for name, url in EMOJIS.items():
            try:
                async with interaction.client.session.get(url) as resp:
                    if resp.status == 200:
                        image_data = await resp.read()
                        await interaction.guild.create_custom_emoji(name=name, image=image_data)
                        success += 1
                        await asyncio.sleep(0.5)  # small delay for rate limiting
                    else:
                        fail += 1
            except Exception:
                fail += 1

        guild_data["emojisAdded"] = "✅"
        await save_data()

        embed = self.make_embed(
            "__EMOJIS ADDED__",
            f"✅ **{success} emojis added successfully!**\n❌ **{fail} failed (possibly duplicates or quota limits).**",
            0x00FF00
        )
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(SetupEmojis(bot))
