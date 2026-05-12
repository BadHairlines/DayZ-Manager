import discord
from discord.ext import commands
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io


class WelcomeGoodbye(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Channel IDs
        self.welcome_channel_id = 1503603498850455655
        self.goodbye_channel_id = 1503603543603413134
        self.rules_channel_id = 1503604467843469444

    # -----------------------------
    # CHANNEL HELPER (SAFE)
    # -----------------------------
    async def fetch_channel(self, channel_id: int):
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            channel = await self.bot.fetch_channel(channel_id)
        return channel

    # -----------------------------
    # MEE6-STYLE IMAGE CREATOR
    # -----------------------------
    async def create_welcome_image(self, member: discord.Member):

        # Background base
        base = Image.new("RGB", (900, 300), "#0f0f1a")
        draw = ImageDraw.Draw(base)

        # Gradient background (smooth MEE6 style)
        for y in range(300):
            r = int(20 + (y * 0.18))
            g = int(25 + (y * 0.12))
            b = int(45 + (y * 0.22))
            draw.line([(0, y), (900, y)], fill=(r, g, b))

        # -----------------------------
        # Avatar download (async safe)
        # -----------------------------
        avatar_url = member.display_avatar.url

        async with self.bot.session.get(avatar_url) as resp:
            avatar_bytes = await resp.read()

        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        avatar = avatar.resize((160, 160))

        # Circle mask
        mask = Image.new("L", (160, 160), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, 160, 160), fill=255)

        # Glow effect (MEE6 ring)
        glow = Image.new("RGBA", (190, 190), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        glow_draw.ellipse((0, 0, 190, 190), fill=(0, 170, 255, 90))
        glow = glow.filter(ImageFilter.GaussianBlur(10))

        base.paste(glow, (40, 70), glow)
        base.paste(avatar, (50, 80), mask)

        # -----------------------------
        # Fonts
        # -----------------------------
        try:
            font_big = ImageFont.truetype("arial.ttf", 42)
            font_mid = ImageFont.truetype("arial.ttf", 28)
            font_small = ImageFont.truetype("arial.ttf", 22)
        except:
            font_big = ImageFont.load_default()
            font_mid = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # -----------------------------
        # Card panel (center UI box)
        # -----------------------------
        card = Image.new("RGBA", (560, 180), (0, 0, 0, 140))
        card = card.filter(ImageFilter.GaussianBlur(0))
        base.paste(card, (240, 60), card)

        # -----------------------------
        # Text (MEE6 hierarchy style)
        # -----------------------------
        draw.text((260, 85), "WELCOME", fill=(120, 200, 255), font=font_small)

        draw.text(
            (260, 115),
            member.name,
            fill="white",
            font=font_big
        )

        draw.text(
            (260, 170),
            f"Member #{member.guild.member_count}",
            fill=(200, 200, 200),
            font=font_mid
        )

        draw.text(
            (260, 205),
            "Glad to have you here!",
            fill=(160, 160, 160),
            font=font_small
        )

        # Output buffer
        buffer = io.BytesIO()
        base.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    # -----------------------------
    # WELCOME
    # -----------------------------
    async def send_welcome(self, member: discord.Member):
        channel = await self.fetch_channel(self.welcome_channel_id)

        image = await self.create_welcome_image(member)
        file = discord.File(image, filename="welcome.png")

        await channel.send(
            content=f"👋 Welcome {member.mention} to The Hive!",
            file=file
        )

    # -----------------------------
    # GOODBYE
    # -----------------------------
    async def send_goodbye(self, member: discord.Member):
        channel = await self.fetch_channel(self.goodbye_channel_id)

        embed = discord.Embed(
            title="🚪 Member Left",
            description=f"**{member.name}** has left the server.",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Now {member.guild.member_count} members")

        await channel.send(embed=embed)

    # -----------------------------
    # EVENTS
    # -----------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self.send_welcome(member)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await self.send_goodbye(member)

    # -----------------------------
    # TEST COMMANDS
    # -----------------------------
    @commands.command()
    async def test_welcome(self, ctx):
        await self.send_welcome(ctx.author)

    @commands.command()
    async def test_goodbye(self, ctx):
        await self.send_goodbye(ctx.author)


async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeGoodbye(bot))
