import discord
from discord.ext import commands
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont
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
    # IMAGE CREATOR (ASYNC SAFE)
    # -----------------------------
    async def create_welcome_image(self, member: discord.Member):
        base = Image.new("RGB", (900, 300), (10, 10, 10))
        draw = ImageDraw.Draw(base)

        # -----------------------------
        # Avatar download (NO requests blocking)
        # -----------------------------
        avatar_url = member.display_avatar.url

        async with self.bot.session.get(avatar_url) as resp:
            avatar_bytes = await resp.read()

        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        avatar = avatar.resize((180, 180))

        # Circle mask
        mask = Image.new("L", (180, 180), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, 180, 180), fill=255)

        base.paste(avatar, (40, 60), mask)

        # Fonts
        try:
            font_big = ImageFont.truetype("arial.ttf", 40)
            font_small = ImageFont.truetype("arial.ttf", 25)
        except:
            font_big = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # Text
        draw.text((250, 80), member.name, fill="white", font=font_big)
        draw.text((250, 140), "just joined the server", fill="gray", font=font_small)
        draw.text(
            (250, 190),
            f"Member #{member.guild.member_count}",
            fill="lightgray",
            font=font_small
        )

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
