import random
import discord
from discord import app_commands
from discord.ext import commands

# ========= Slap Buttons View =========
class SlapView(discord.ui.View):
    def __init__(self, author: discord.Member, target: discord.Member, slap_lines, gif_urls):
        super().__init__(timeout=60)
        self.author = author
        self.target = target
        self.slap_lines = slap_lines
        self.gif_urls = gif_urls

    @discord.ui.button(label="Retaliate!", style=discord.ButtonStyle.danger)
    async def retaliate(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message(
                "You can't retaliate for someone else! 😆", ephemeral=True
            )

        # Random slap GIF + message for retaliation
        text = random.choice(self.slap_lines).format(author=self.target.mention)
        gif = random.choice(self.gif_urls)
        embed = discord.Embed(description=text, color=0xFF0000)
        embed.set_image(url=gif)
        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        embed.timestamp = discord.utils.utcnow()

        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="😂 React", style=discord.ButtonStyle.secondary)
    async def react(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.message.add_reaction("😂")
        await interaction.response.send_message("Reacted with 😂", ephemeral=True)


# ========= Slap Cog =========
class Slap(commands.Cog):
    """Fun slap command with GIFs, buttons, and epic moments."""

    slap_lines = [
        "You just got folded like a lawn chair by {author} 💀",
        "You just got bitch slapped by {author} 🤣",
        "You just got slapped outta existence by {author} 🤯",
        "{author} just slapped the sense outta you 😵‍💫",
        "{author} just gave you that “sit down” energy 😭",
        "{author} just hit you so hard your ancestors felt it 💢",
        "BOOM! {author} just rocked your whole existence 🤯",
    ]

    epic_slaps = [
        "🔥 EPIC SLAP! {author} sent {target} to another dimension! 🌌",
        "💥 CRITICAL HIT! {author} unleashed ultimate slap power on {target}! 💫",
    ]

    gif_urls = [
        "https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExMG13YTFqaWMwaG1iNGh0d25wN25kbXkzcmd0ajI1bW81OWRoejVhOCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/gSIz6gGLhguOY/giphy.gif",
        "https://media2.giphy.com/media/jBmxgqWuiOZ9xb3Ria/giphy.gif?cid=6c09b952mfbniedh8w4wo4b2lq3dlh09hr3yspta73mgcy8j&ep=v1_internal_gif_by_id&rid=giphy.gif&ct=g",
        "https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExajh2d2xyb2Q3bWdpcWxzc2RwYXhmODd1YTA0dWFoZTB5YnM2ZW9xMyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3XlEk2RxPS1m8/giphy.gif",
        "https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExbWU2aGFwcjJsaTJ2dmpjcHB0ejVvdmIyemRocHJkMm1tcnF4ajgzbyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/htiVRuP7N0XK/giphy.gif",
    ]

    epic_gifs = [
        "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif",
        "https://media.giphy.com/media/3o6ZsYw9K6oiLQwZrC/giphy.gif",
    ]

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="slap",
        description="Playfully slap another user with a spicy message and GIF."
    )
    @app_commands.describe(user="Who are you trying to slap?")
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def slap(self, interaction: discord.Interaction, user: discord.Member):
        author = interaction.user

        if user.id == author.id:
            text = f"{author.mention}, slapping yourself? That’s… ambitious 😵‍💫"
            embed = discord.Embed(description=text, color=0xFF4500)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Chance for epic slap (10%)
        is_epic = random.random() < 0.1
        if is_epic:
            text = random.choice(self.epic_slaps).format(author=author.mention, target=user.mention)
            gif = random.choice(self.epic_gifs)
            color = 0xFFD700
        else:
            text = random.choice(self.slap_lines).format(author=author.mention)
            gif = random.choice(self.gif_urls)
            color = 0xFF0000

        embed = discord.Embed(description=text, color=color)
        embed.set_image(url=gif)
        embed.set_footer(text="DayZ Manager", icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png")
        embed.timestamp = discord.utils.utcnow()

        # Send message with buttons
        await interaction.response.send_message(
            content=user.mention,
            embed=embed,
            view=SlapView(author, user, self.slap_lines, self.gif_urls),
            allowed_mentions=discord.AllowedMentions(users=True)
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Slap(bot))
