import discord
from discord import app_commands
from discord.ext import commands


class RoleList(commands.Cog):
    """Show everyone who has a specific Discord role."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

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
        # Make sure we have a guild
        if interaction.guild is None:
            return await interaction.response.send_message(
                "This command can only be used inside a server.",
                ephemeral=True
            )

        # Fetch EVERY member from Discord
        members = [
            member async for member in interaction.guild.fetch_members(limit=None)
        ]

        # Find everyone with the selected role
        role_members = [
            member for member in members
            if role in member.roles
        ]

        # No members
        if not role_members:
            embed = discord.Embed(
                title=f"{role.name}",
                description="No members currently have this role.",
                color=role.color if role.color.value else discord.Color.blurple()
            )

            embed.set_footer(
                text="DayZ Manager",
                icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
            )

            return await interaction.response.send_message(embed=embed)

        # Sort alphabetically
        role_members.sort(key=lambda member: member.display_name.lower())

        # Create member list
        member_list = "\n".join(
            f"• {member.mention}"
            for member in role_members
        )

        embed = discord.Embed(
            title=f"{role.name}",
            description=member_list,
            color=role.color if role.color.value else discord.Color.blurple()
        )

        embed.add_field(
            name="Members",
            value=str(len(role_members)),
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
