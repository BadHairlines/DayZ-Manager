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

class Todo(
    commands.Cog
):

    def __init__(
        self,
        bot: commands.Bot,
    ):

        self.bot = bot

    # =====================================================
    # STAFF CHECK
    # =====================================================

    @staticmethod
    def is_staff(
        member: discord.Member,
    ) -> bool:

        if member.guild_permissions.administrator:
            return True

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
            title="📋  THE HIVE STAFF TO-DO",
            description=(
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "Staff task management board.\n"
                "Use the buttons below to create, "
                "manage, and track staff tasks.\n"
            ),
            color=EMBED_COLOR,
        )

        # =================================================
        # TASKS
        # =================================================

        if not tasks:

            embed.add_field(
                name="📭  ALL CLEAR",
                value=(
                    "There are currently **no open tasks.**\n\n"
                    "Everything is up to date! 🎉"
                ),
                inline=False,
            )

        else:

            grouped = {
                "critical": [],
                "high": [],
                "medium": [],
                "low": [],
            }

            for task in tasks:

                priority = task["priority"]

                grouped.setdefault(
                    priority,
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

                    assignee = (
                        f"<@{assigned}>"
                        if assigned
                        else "*Unassigned*"
                    )

                    if task["due_at"]:

                        if (
                            task["due_at"]
                            < discord.utils.utcnow()
                        ):

                            due = (
                                f" • 🚨 "
                                f"**OVERDUE "
                                f"{discord.utils.format_dt(task['due_at'], 'R')}**"
                            )

                        else:

                            due = (
                                f" • 📅 "
                                f"{discord.utils.format_dt(task['due_at'], 'R')}"
                            )

                    else:

                        due = ""

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

        overdue = stats["overdue_count"]

        overdue_line = ""

        if overdue:

            overdue_line = (
                f"\n🚨 **{overdue}** Overdue"
            )

        embed.add_field(
            name="📊 TASK OVERVIEW",
            value=(
                f"📝 **{stats['open_count']}** Open"
                f"   •   "
                f"✅ **{stats['completed_count']}** Completed"
                f"   •   "
                f"📋 **{stats['total_count']}** Total\n\n"
                f"🔴 **{stats['critical_count']}** Critical"
                f"   •   "
                f"🟠 **{stats['high_count']}** High\n"
                f"🟡 **{stats['medium_count']}** Medium"
                f"   •   "
                f"🟢 **{stats['low_count']}** Low"
                f"{overdue_line}"
            ),
            inline=False,
        )

        # =================================================
        # FOOTER
        # =================================================

        embed.set_footer(
            text=(
                "DayZ Manager  •  "
                "Staff To-Do Management"
            ),
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

        if not guild:
            return False

        board = await database.get_board(
            str(guild.id)
        )

        if not board:
            return False

        try:

            channel = guild.get_channel(
                int(board["channel_id"])
            )

        except (
            TypeError,
            ValueError,
        ):

            return False

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
    # SETUP
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

            await interaction.response.send_message(
                "❌ This command can only be used "
                "inside a server.",
                ephemeral=True,
            )

            return

        if not isinstance(
            interaction.user,
            discord.Member,
        ):

            await interaction.response.send_message(
                "❌ Unable to verify your permissions.",
                ephemeral=True,
            )

            return

        if not interaction.user.guild_permissions.administrator:

            await interaction.response.send_message(
                "❌ Only server administrators can "
                "create the To-Do board.",
                ephemeral=True,
            )

            return

        if not isinstance(
            interaction.channel,
            discord.TextChannel,
        ):

            await interaction.response.send_message(
                "❌ The To-Do board must be created "
                "inside a text channel.",
                ephemeral=True,
            )

            return

        await interaction.response.defer(
            ephemeral=True
        )

        await database.ensure_connection()

        # =================================================
        # CHECK EXISTING BOARD
        # =================================================

        existing = await database.get_board(
            str(interaction.guild.id)
        )

        if existing:

            try:

                channel = interaction.guild.get_channel(
                    int(existing["channel_id"])
                )

            except (
                TypeError,
                ValueError,
            ):

                channel = None

            if isinstance(
                channel,
                discord.TextChannel,
            ):

                try:

                    message = await channel.fetch_message(
                        int(existing["message_id"])
                    )

                    await interaction.followup.send(
                        (
                            "⚠️ A To-Do board already exists "
                            f"in {channel.mention}.\n\n"
                            f"[Jump to board]({message.jump_url})"
                        ),
                        ephemeral=True,
                    )

                    return

                except (
                    discord.NotFound,
                    discord.Forbidden,
                    discord.HTTPException,
                ):

                    pass

        # =================================================
        # CREATE BOARD
        # =================================================

        embed = await self.create_embed(
            interaction.guild
        )

        try:

            message = await interaction.channel.send(
                embed=embed,
                view=TodoView(self),
            )

        except discord.Forbidden:

            await interaction.followup.send(
                "❌ I don't have permission to send "
                "messages in this channel.",
                ephemeral=True,
            )

            return

        except discord.HTTPException:

            await interaction.followup.send(
                "❌ Discord rejected the board message.",
                ephemeral=True,
            )

            return

        # =================================================
        # SAVE BOARD
        # =================================================

        await database.save_board(
            guild_id=str(
                interaction.guild.id
            ),
            channel_id=str(
                interaction.channel.id
            ),
            message_id=str(
                message.id
            ),
        )

        await interaction.followup.send(
            (
                "✅ **To-Do board created!**\n\n"
                f"{message.jump_url}"
            ),
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
    # Initialize this system's own PostgreSQL database.
    # -----------------------------------------------------

    await database.ensure_connection()

    # -----------------------------------------------------
    # Register persistent buttons.
    # -----------------------------------------------------

    bot.add_view(
        TodoView(cog)
    )
