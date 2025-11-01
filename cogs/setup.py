import discord
from discord import app_commands, Interaction, Embed
from discord.ext import commands
from cogs.utils import FLAGS, MAP_DATA, CUSTOM_EMOJIS, set_flag, get_all_flags
import asyncio


class Setup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Setup a map and initialize all flags in the database.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(selected_map="Select the map to setup (Livonia, Chernarus, Sakhal)")
    @app_commands.choices(selected_map=[
        app_commands.Choice(name="Livonia", value="livonia"),
        app_commands.Choice(name="Chernarus", value="chernarus"),
        app_commands.Choice(name="Sakhal", value="sakhal"),
    ])
    async def setup(self, interaction: Interaction, selected_map: app_commands.Choice[str]):
        guild = interaction.guild
        guild_id = str(guild.id)
        map_key = selected_map.value
        map_info = MAP_DATA[map_key]
        channel_name = f"flags-{map_key}"

        # ✅ Initial progress message
        await interaction.response.send_message(
            f"⚙️ Setting up **{map_info['name']}** flags... please wait ⏳",
            ephemeral=True
        )

        try:
            # ✅ Create or find channel
            existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
            if existing_channel:
                setup_channel = existing_channel
            else:
                setup_channel = await guild.create_text_channel(
                    name=channel_name,
                    reason=f"Auto-created for {map_info['name']} setup"
                )
                await setup_channel.send(
                    f"📜 This channel displays flag ownership for **{map_info['name']}**."
                )

            # ✅ Initialize all flags
            for flag in FLAGS:
                await set_flag(guild_id, map_key, flag, "✅", None)
                await asyncio.sleep(0.05)

            # ✅ Fetch initialized data for flag embed
            records = await get_all_flags(guild_id, map_key)
            db_flags = {r["flag"]: r for r in records}

            embed = Embed(
                title=f"**———⛳️ {map_info['name'].upper()} FLAGS ⛳️———**",
                color=0x86DC3D
            )
            embed.set_author(name="🚨 Flags Notification 🚨")
            embed.set_footer(
                text="DayZ Manager",
                icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
            )
            embed.timestamp = discord.utils.utcnow()

            # ✅ Build flag list
            lines = []
            for flag in FLAGS:
                data = db_flags.get(flag)
                status = data["status"] if data else "✅"
                role_id = data["role_id"] if data and data["role_id"] else None
                emoji = CUSTOM_EMOJIS.get(flag, "")
                if not emoji.startswith("<:"):
                    emoji = ""
                display_value = "✅" if status == "✅" else (f"<@&{role_id}>" if role_id else "❌")
                lines.append(f"{emoji} **• {flag}**: {display_value}")
            embed.description = "\n".join(lines)

            # ✅ Post flag embed into the channel
            await setup_channel.send(embed=embed)

            # ✅ Final confirmation message (edit original)
            complete_embed = Embed(
                title="__SETUP COMPLETE__",
                description=(
                    f"✅ **{map_info['name']}** setup finished successfully.\n\n"
                    f"📁 Flags channel created: {setup_channel.mention}\n"
                    f"All flags have been initialized and displayed in that channel."
                ),
                color=0x00FF00
            )
            complete_embed.set_image(url=map_info["image"])
            complete_embed.set_author(name="🚨 Setup Notification 🚨")
            complete_embed.set_footer(
                text="DayZ Manager",
                icon_url="https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
            )
            complete_embed.timestamp = discord.utils.utcnow()

            await interaction.edit_original_response(content=None, embed=complete_embed)

        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ Setup failed for **{map_info['name']}**:\n```{e}```"
            )

    @setup.error
    async def setup_error(self, interaction: Interaction, error):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message(
                "🚫 This command is for admins ONLY!", ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"❌ An unexpected error occurred:\n```{error}```",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Setup(bot))
