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
    # CLEAN CENTERED WELCOME IMAGE
    # -----------------------------
    async def create_welcome_image(self, member: discord.Member):

        # Pure black background
        base = Image.new("RGB", (900, 300), (0, 0, 0))
        draw = ImageDraw.Draw(base)

        # -----------------------------
        # AVATAR (CENTER TOP)
        # -----------------------------
        avatar_url = member.display_avatar.url

        async with self.bot.session.get(avatar_url) as resp:
            avatar_bytes = await resp.read()

        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        avatar = avatar.resize((140, 140))

        # Circle mask
        mask = Image.new("L", (140, 140), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, 140, 140), fill=255)

        # Center position
        avatar_x = (900 - 140) // 2
        avatar_y = 30

        # Glow ring
        glow = Image.new("RGBA", (170, 170), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        glow_draw.ellipse((0, 0, 170, 170), fill=(0, 170, 255, 80))
        glow = glow.filter(ImageFilter.GaussianBlur(8))

        base.paste(glow, (avatar_x - 15, avatar_y - 15), glow)
        base.paste(avatar, (avatar_x, avatar_y), mask)

        # -----------------------------
        # FONTS
        # -----------------------------
        try:
            font_big = ImageFont.truetype("arial.ttf", 42)
            font_mid = ImageFont.truetype("arial.ttf", 26)
            font_small = ImageFont.truetype("arial.ttf", 20)
        except:
            font_big = ImageFont.load_default()
            font_mid = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # -----------------------------
        # CENTERED TEXT STACK
        # -----------------------------

        name_text = member.name
        draw.text(
            ((900 - draw.textlength(name_text, font=font_big)) / 2, 190),
            name_text,
            fill="white",
            font=font_big
        )

        join_text = "just joined the server"
        draw.text(
            ((900 - draw.textlength(join_text, font=font_mid)) / 2, 235),
            join_text,
            fill=(180, 180, 180),
            font=font_mid
        )

        member_text = f"Member #{member.guild.member_count}"
        draw.text(
            ((900 - draw.textlength(member_text, font=font_small)) / 2, 265),
            member_text,
            fill=(120, 120, 120),
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
