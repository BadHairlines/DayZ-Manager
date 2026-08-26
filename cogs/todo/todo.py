from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from . import database
from .views import (
    PRIORITY_EMOJIS,
    TodoView,
)


# =========================================================
# CONFIG
# =========================================================

FOOTER_ICON = (
    "https://i.postimg.cc/rmXpLFpv/ewn60cg6.png"
)

EMBED_COLOR = 0x3498DB


# =========================================================
# TODO COG
# =========================================================

class Todo(commands.Cog):

    def __init__(
        self,
        bot: commands.Bot,
    ):

        self.bot = bot

    # =====================================================
    # STAFF CHECK
    # =====================================================

    def is_staff(
        self,
        member: discord.Member,
    ) -> bool:

        if member.guild_permissions.administrator:
            return True

        # Staff = Manage Server or Manage Messages.
        return (
            member.guild_permissions.manage_guild
            or member.guild_permissions.manage_messages
        )

    # =====================================================
    # BUILD EMBED
    # =====================================================

    async def create_embed(
        self,
        guild: discord.Guild,
    ) -> discord.Embed:

        tasks = await database.get_open_tasks(
            str(guild.id)
        )

        stats = await database.get_task_stats(
            str(guild.id)
        )

        embed = discord.Embed(
            title="📋  THE HIVE TO-DO LIST",
            description=(
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "Staff task management board. "
                "Use the buttons below to manage tasks.\n"
            ),
            color=EMBED_COLOR,
        )

        # =================================================
        # NO TASKS
        # =================================================

        if not tasks:

            embed.description += (
                "\n📭 **No open tasks.**\n\n"
                "Everything is currently up to date! 🎉"
            )

        else:

            grouped = {
                "critical": [],
                "high": [],
                "medium": [],
                "low": [],
            }

            for task in tasks:

                grouped.setdefault(
                    task["priority"],
                    [],
                ).append(task)

            for priority in (
                "critical",
                "high",
                "medium",
                "low",
            ):

                priority_tasks = grouped.get(
                    priority,
                    [],
                )

                if not priority_tasks:
                    continue

                lines = []

                emoji = PRIORITY_EMOJIS.get(
                    priority,
                    "📋",
                )

                for task in priority_tasks:

                    assigned = task["assigned_to"]

                    if assigned:
                        assignee = (
                            f"<@{assigned}>"
                        )
                    else:
                        assignee = (
                            "*Unassigned*"
                        )

                    due = ""

                    if task["due_at"]:

                        due = (
                            f" • 📅 "
                            f"<t:{int(task['due_at'].timestamp())}:R>"
                        )

                    lines.append(
                        f"❌ **{task['title']}**\n"
                        f"   👤 {assignee}"
                        f"{due}"
                    )

                value = "\n\n".join(
                    lines
                )

                if len(value) > 1024:
                    value = (
                        value[:1000]
                        + "\n..."
                    )

                embed.add_field(
                    name=(
                        f"{emoji} "
                        f"{priority.upper()} PRIORITY"
                    ),
                    value=value,
                    inline=False,
                )

        # =================================================
        # STATISTICS
        # =================================================

        embed.add_field(
            name="📊 TASK STATISTICS",
            value=(
                f"📝 **{stats['open_count']}** Open"
                f"   •   "
                f"✅ **{stats['completed_count']}** Completed"
                f"   •   "
                f"📋 **{stats['total_count']}** Total\n\n"
                f"🔴 {stats['critical_count']} Critical"
                f"   •   "
                f"🟠 {stats['high_count']} High"
                f"   •   "
                f"🟡 {stats['medium_count']} Medium"
                f"   •   "
                f"🟢 {stats['low_count']} Low"
            ),
            inline=False,
        )

        embed.set_footer(
            text="DayZ Manager  •  Staff To-Do Management",
            icon_url=FOOTER_ICON,
        )

        embed.timestamp = discord.utils.utcnow()

        return embed

    # =====================================================
    # REFRESH BOARD
    # =====================================================

    async def refresh_board(
        self,
        guild: discord.Guild,
    ) -> bool:

        board = await database.get_board(
            str(guild.id)
        )

        if not board:
            return False

        channel = guild.get_channel(
            int(board["channel_id"])
        )

        if not isinstance(
            channel,
            discord.TextChannel,
        ):
            return False

        try:

            message = await channel.fetch_message(
                int(board["message_id"])
            )

            embed = await self.create_embed(
                guild
            )

            await message.edit(
                embed=embed,
                view=TodoView(self),
            )

            return True

        except (
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException,
        ):

            return False

    # =====================================================
    # SETUP COMMAND
    # =====================================================

    @app_commands.command(
        name="todosetup",
        description="Create the staff To-Do board.",
    )
    @app_commands.default_permissions(
        administrator=True
    )
    async def todosetup(
        self,
        interaction: discord.Interaction,
    ):

        if not interaction.guild:
            return

        await interaction.response.defer(
            ephemeral=True
        )

        # -------------------------------------------------
        # Make sure the To-Do database is ready.
        # -------------------------------------------------

        await database.ensure_connection()

        # -------------------------------------------------
        # Prevent accidental duplicate boards.
        # -------------------------------------------------

        existing = await database.get_board(
            str(interaction.guild.id)
        )

        if existing:

            channel = interaction.guild.get_channel(
                int(existing["channel_id"])
            )

            if isinstance(
                channel,
                discord.TextChannel,
            ):

                try:

                    message = await channel.fetch_message(
                        int(existing["message_id"])
                    )

                    await interaction.followup.send(
                        "⚠️ A To-Do board already exists "
                        f"in {channel.mention}.\n"
                        f"[Jump to board]({message.jump_url})",
                        ephemeral=True,
                    )

                    return

                except (
                    discord.NotFound,
                    discord.Forbidden,
                ):
                    pass

        # -------------------------------------------------
        # Build board.
        # -------------------------------------------------

        embed = await self.create_embed(
            interaction.guild
        )

        message = await interaction.channel.send(
            embed=embed,
            view=TodoView(self),
        )

        # -------------------------------------------------
        # Save board location.
        # -------------------------------------------------

        await database.save_board(
            guild_id=str(interaction.guild.id),
            channel_id=str(interaction.channel.id),
            message_id=str(message.id),
        )

        await interaction.followup.send(
            f"✅ To-Do board created: {message.jump_url}",
            ephemeral=True,
        )


# =========================================================
# SETUP
# =========================================================

async def setup(
    bot: commands.Bot,
):

    cog = Todo(bot)

    await bot.add_cog(
        cog
    )

    # -----------------------------------------------------
    # Initialize the To-Do database.
    # -----------------------------------------------------

    await database.ensure_connection()

    # -----------------------------------------------------
    # Register persistent To-Do buttons.
    # -----------------------------------------------------

    bot.add_view(
        TodoView(cog)
    )
