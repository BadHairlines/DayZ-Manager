import discord
from discord import app_commands
from discord.ext import commands


class RoleList(commands.Cog):
    """Show everyone who has a specific Discord role."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ========= /rolelist =========
    @app_commands.command(
        name="rolelist",
        description="Show everyone who has a specific role."
    )
    @app_commands.describe(
        role="The role you want to see members of."
    )
    async def rolelist(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        # Get all members with the selected role
        members = [member for member in interaction.guild.members if role in member.roles]

        # No members have the role
        if not members:
            embed = discord.Embed(
                title=f"{role.name}",
                description="No members currently have this role.",
                color=role.color if role.color.value else discord.Color.blurple()
            )

            embed.set_footer(
                text="DayZ Manager",
                icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
            )
            embed.timestamp = discord.utils.utcnow()

            return await interaction.response.send_message(embed=embed)

        # Create member list
        member_list = "\n".join(
            f"• {member.mention}"
            for member in members
        )

        embed = discord.Embed(
            title=f"{role.name}",
            description=member_list,
            color=role.color if role.color.value else discord.Color.blurple()
        )

        embed.add_field(
            name="Members",
            value=f"**{len(members)}**",
            inline=True
        )

        embed.set_footer(
            text="DayZ Manager",
            icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
        )
        embed.timestamp = discord.utils.utcnow()

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleList(bot))
