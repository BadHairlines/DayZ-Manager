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
    # HD WELCOME IMAGE (MAX SIZE)
    # -----------------------------
    async def create_welcome_image(self, member: discord.Member):

        # HD canvas
        W, H = 1920, 640
        base = Image.new("RGB", (W, H), (0, 0, 0))
        draw = ImageDraw.Draw(base)

        # -----------------------------
        # AVATAR
        # -----------------------------
        avatar_url = member.display_avatar.url

        async with self.bot.session.get(avatar_url) as resp:
            avatar_bytes = await resp.read()

        avatar_size = 260
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        avatar = avatar.resize((avatar_size, avatar_size))

        # Circle mask
        mask = Image.new("L", (avatar_size, avatar_size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)

        # Center position
        avatar_x = (W - avatar_size) // 2
        avatar_y = 70

        # Glow ring
        glow_size = avatar_size + 80
        glow = Image.new("RGBA", (glow_size, glow_size), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        glow_draw.ellipse(
            (0, 0, glow_size, glow_size),
            fill=(0, 170, 255, 90)
        )
        glow = glow.filter(ImageFilter.GaussianBlur(20))

        base.paste(glow, (avatar_x - 40, avatar_y - 40), glow)
        base.paste(avatar, (avatar_x, avatar_y), mask)

        # -----------------------------
        # FONTS (SCALED FOR HD)
        # -----------------------------
        try:
            font_big = ImageFont.truetype("arial.ttf", 84)
            font_mid = ImageFont.truetype("arial.ttf", 48)
            font_small = ImageFont.truetype("arial.ttf", 34)
        except:
            font_big = ImageFont.load_default()
            font_mid = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # -----------------------------
        # CENTERED TEXT
        # -----------------------------

        name_text = member.name
        draw.text(
            ((W - draw.textlength(name_text, font=font_big)) / 2, 380),
            name_text,
            fill="white",
            font=font_big
        )

        join_text = "just joined the server"
        draw.text(
            ((W - draw.textlength(join_text, font=font_mid)) / 2, 470),
            join_text,
            fill=(180, 180, 180),
            font=font_mid
        )

        member_text = f"Member #{member.guild.member_count}"
        draw.text(
            ((W - draw.textlength(member_text, font=font_small)) / 2, 540),
            member_text,
            fill=(120, 120, 120),
            font=font_small
        )

        # Output
        buffer = io.BytesIO()
        base.save(buffer, format="PNG", optimize=True)
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
