import random
import discord
from discord import app_commands
from discord.ext import commands


class Slap(commands.Cog):
    """Slap / Slap Command."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ========= /slap =========
    @app_commands.command(
        name="slap",
        description="Playfully slap another user with a spicy message and GIF."
    )
    @app_commands.describe(
        user="Who are you trying to slap?"
    )
    async def slap(self, interaction: discord.Interaction, user: discord.Member):
        author = interaction.user

        # Can't slap yourself
        if user.id == author.id:
            return await interaction.response.send_message(
                "**You can't slap yourself!** 😆",
                ephemeral=True
            )

        # Random slap text variants
        slap_lines = [
            f"You just got folded like a lawn chair by {author.mention}. 💀",
            f"You just got bitch slapped by {author.mention}. 🤣",
            f"You just got slapped outta existence by {author.mention}. 🤯",
            f"{author.mention} just slapped the sense outta you. 😵‍💫",
            f"{author.mention} just gave you that “sit down” energy. 😭",
            f"{author.mention} just hit you so hard your ancestors felt it. 💢",
            f"BOOM! {author.mention} just rocked your whole existence. 🤯",
        ]
        text = random.choice(slap_lines)

        # Random slap GIFs
        gif_urls = [
            "https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExMG13YTFqaWMwaG1iNGh0d25wN25kbXkzcmd0ajI1bW81OWRoejVhOCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/gSIz6gGLhguOY/giphy.gif",
            "https://media2.giphy.com/media/jBmxgqWuiOZ9xb3Ria/giphy.gif?cid=6c09b952mfbniedh8w4wo4b2lq3dlh09hr3yspta73mgcy8j&ep=v1_internal_gif_by_id&rid=giphy.gif&ct=g",
            "https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExajh2d2xyb2Q3bWdpcWxzc2RwYXhmODd1YTA0dWFoZTB5YnM2ZW9xMyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3XlEk2RxPS1m8/giphy.gif",
            "https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExbWU2aGFwcjJsaTJ2dmpjcHB0ejVvdmIyemRocHJkMm1tcnF4ajgzbyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/htiVRuP7N0XK/giphy.gif",
        ]
        gif = random.choice(gif_urls)

        # Build embed
        embed = discord.Embed(
            description=text,
            color=random.randint(0, 0xFFFFFF),
        )
        embed.set_image(url=gif)
        embed.set_footer(
            text="DayZ Manager",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )
        embed.timestamp = discord.utils.utcnow()

        # Reply in channel, pinging only the target like your original
        await interaction.response.send_message(
            content=user.mention,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(slap(bot))
