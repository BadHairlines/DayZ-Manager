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
        # Immediately acknowledge the command
        await interaction.response.defer()

        # Make sure we're in a server
        if interaction.guild is None:
            return await interaction.followup.send(
                "This command can only be used inside a server.",
                ephemeral=True
            )

        try:
            # Fetch EVERY member from Discord
            members = [
                member
                async for member in interaction.guild.fetch_members(limit=None)
            ]

            # Find everyone with the selected role
            role_members = [
                member
                for member in members
                if role in member.roles
            ]

            # Sort alphabetically
            role_members.sort(
                key=lambda member: member.display_name.lower()
            )

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

                embed.timestamp = discord.utils.utcnow()

                return await interaction.followup.send(embed=embed)

            # Build member list
            member_list = "\n".join(
                f"• {member.mention}"
                for member in role_members
            )

            # Discord embeds have a 4096 character description limit
            # So split the list if needed
            chunks = []

            while member_list:
                if len(member_list) <= 4000:
                    chunks.append(member_list)
                    break

                split_at = member_list.rfind("\n", 0, 4000)

                if split_at == -1:
                    split_at = 4000

                chunks.append(member_list[:split_at])
                member_list = member_list[split_at:].lstrip("\n")

            # Send each chunk
            for index, chunk in enumerate(chunks):

                embed = discord.Embed(
                    title=f"{role.name} — Members",
                    description=chunk,
                    color=role.color if role.color.value else discord.Color.blurple()
                )

                # Only show count on first embed
                if index == 0:
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

                await interaction.followup.send(embed=embed)

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I don't have permission to fetch the server members.",
                ephemeral=True
            )

        except discord.HTTPException as e:
            await interaction.followup.send(
                f"❌ Discord returned an error while fetching members:\n`{e}`",
                ephemeral=True
            )

        except Exception as e:
            print(f"RoleList Error: {e}")

            await interaction.followup.send(
                "❌ Something went wrong while fetching the role members.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleList(bot))
