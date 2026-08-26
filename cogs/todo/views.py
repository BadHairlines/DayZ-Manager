from __future__ import annotations

import re
from datetime import datetime, timezone

import discord

from . import database


# =========================================================
# CONFIG
# =========================================================

EMBED_COLOR = 0x3498DB

PRIORITY_EMOJIS = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
}

PRIORITY_LABELS = {
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}


# =========================================================
# HELPERS
# =========================================================

def parse_user_id(
    value: str | None,
) -> str | None:

    if not value:
        return None

    value = value.strip()

    match = re.search(
        r"\d{15,25}",
        value,
    )

    if not match:
        return None

    return match.group(0)


def parse_due_date(
    value: str | None,
):

    if not value:
        return None

    value = value.strip()

    if not value:
        return None

    formats = (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
    )

    for fmt in formats:

        try:

            parsed = datetime.strptime(
                value,
                fmt,
            )

            return parsed.replace(
                tzinfo=timezone.utc
            )

        except ValueError:
            continue

    return None


def discord_timestamp(
    value,
    style: str = "R",
) -> str:

    if not value:
        return ""

    return (
        f"<t:{int(value.timestamp())}:{style}>"
    )


def is_overdue(
    task,
) -> bool:

    return bool(
        task["due_at"]
        and task["status"] == "open"
        and task["due_at"]
        < datetime.now(timezone.utc)
    )


def task_assignee(
    task,
) -> str:

    if task["assigned_to"]:
        return (
            f"<@{task['assigned_to']}>"
        )

    return "*Unassigned*"


# =========================================================
# ADD TASK MODAL
# =========================================================

class AddTaskModal(
    discord.ui.Modal
):

    def __init__(
        self,
        cog,
    ):

        super().__init__(
            title="Create New Task"
        )

        self.cog = cog

        self.title_input = discord.ui.TextInput(
            label="Task Name",
            placeholder="What needs to be done?",
            max_length=100,
            required=True,
        )

        self.description_input = discord.ui.TextInput(
            label="Description",
            placeholder="Optional task details...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=False,
        )

        self.priority_input = discord.ui.TextInput(
            label="Priority",
            placeholder="critical / high / medium / low",
            max_length=10,
            required=True,
            default="medium",
        )

        self.due_input = discord.ui.TextInput(
            label="Due Date",
            placeholder="YYYY-MM-DD HH:MM (UTC) or leave blank",
            max_length=19,
            required=False,
        )

        self.assignee_input = discord.ui.TextInput(
            label="Assign To",
            placeholder="@user, user ID, or leave blank",
            max_length=30,
            required=False,
        )

        self.add_item(
            self.title_input
        )

        self.add_item(
            self.description_input
        )

        self.add_item(
            self.priority_input
        )

        self.add_item(
            self.due_input
        )

        self.add_item(
            self.assignee_input
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):

        priority = (
            self.priority_input.value
            .strip()
            .lower()
        )

        if priority not in PRIORITY_LABELS:

            await interaction.response.send_message(
                "❌ Invalid priority.\n\n"
                "Use: `critical`, `high`, `medium`, or `low`.",
                ephemeral=True,
            )

            return

        due_at = parse_due_date(
            self.due_input.value
        )

        if (
            self.due_input.value.strip()
            and due_at is None
        ):

            await interaction.response.send_message(
                "❌ Invalid due date.\n\n"
                "Use `YYYY-MM-DD HH:MM` in UTC.",
                ephemeral=True,
            )

            return

        assigned_to = parse_user_id(
            self.assignee_input.value
        )

        if assigned_to:

            member = interaction.guild.get_member(
                int(assigned_to)
            )

            if not member:

                await interaction.response.send_message(
                    "❌ I couldn't find that Discord member "
                    "in this server.",
                    ephemeral=True,
                )

                return

        task = await database.create_task(
            guild_id=str(
                interaction.guild_id
            ),
            title=self.title_input.value.strip(),
            description=(
                self.description_input.value.strip()
                or None
            ),
            created_by=str(
                interaction.user.id
            ),
            assigned_to=assigned_to,
            priority=priority,
            due_at=due_at,
        )

        await interaction.response.send_message(
            (
                "✅ **Task created successfully.**\n\n"
                f"📋 **{task['title']}**\n"
                f"{PRIORITY_EMOJIS[priority]} "
                f"**{PRIORITY_LABELS[priority]}**\n"
                f"👤 {task_assignee(task)}"
            ),
            ephemeral=True,
        )

        await self.cog.refresh_board(
            interaction.guild
        )


# =========================================================
# EDIT TASK MODAL
# =========================================================

class EditTaskModal(
    discord.ui.Modal
):

    def __init__(
        self,
        cog,
        task,
    ):

        super().__init__(
            title="Edit Task"
        )

        self.cog = cog
        self.task = task

        self.title_input = discord.ui.TextInput(
            label="Task Name",
            max_length=100,
            required=True,
            default=task["title"],
        )

        self.description_input = discord.ui.TextInput(
            label="Description",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=False,
            default=task["description"] or "",
        )

        self.priority_input = discord.ui.TextInput(
            label="Priority",
            max_length=10,
            required=True,
            default=task["priority"],
        )

        existing_due = ""

        if task["due_at"]:

            existing_due = (
                task["due_at"]
                .astimezone(timezone.utc)
                .strftime(
                    "%Y-%m-%d %H:%M"
                )
            )

        self.due_input = discord.ui.TextInput(
            label="Due Date",
            placeholder="YYYY-MM-DD HH:MM (UTC)",
            max_length=19,
            required=False,
            default=existing_due,
        )

        self.assignee_input = discord.ui.TextInput(
            label="Assign To",
            placeholder="@user, user ID, or blank",
            max_length=30,
            required=False,
            default=(
                task["assigned_to"]
                or ""
            ),
        )

        self.add_item(
            self.title_input
        )

        self.add_item(
            self.description_input
        )

        self.add_item(
            self.priority_input
        )

        self.add_item(
            self.due_input
        )

        self.add_item(
            self.assignee_input
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):

        priority = (
            self.priority_input.value
            .strip()
            .lower()
        )

        if priority not in PRIORITY_LABELS:

            await interaction.response.send_message(
                "❌ Invalid priority.",
                ephemeral=True,
            )

            return

        due_at = parse_due_date(
            self.due_input.value
        )

        if (
            self.due_input.value.strip()
            and due_at is None
        ):

            await interaction.response.send_message(
                "❌ Invalid due date.\n"
                "Use `YYYY-MM-DD HH:MM` in UTC.",
                ephemeral=True,
            )

            return

        assigned_to = parse_user_id(
            self.assignee_input.value
        )

        if assigned_to:

            member = interaction.guild.get_member(
                int(assigned_to)
            )

            if not member:

                await interaction.response.send_message(
                    "❌ That member isn't in this server.",
                    ephemeral=True,
                )

                return

        result = await database.update_task(
            guild_id=str(
                interaction.guild_id
            ),
            task_id=int(
                self.task["id"]
            ),
            title=self.title_input.value.strip(),
            description=(
                self.description_input.value.strip()
                or None
            ),
            assigned_to=assigned_to,
            priority=priority,
            due_at=due_at,
        )

        if not result:

            await interaction.response.send_message(
                "❌ That task no longer exists or "
                "has already been completed.",
                ephemeral=True,
            )

            return

        await interaction.response.send_message(
            "✅ **Task updated successfully.**",
            ephemeral=True,
        )

        await self.cog.refresh_board(
            interaction.guild
        )


# =========================================================
# TASK DETAILS EMBED
# =========================================================

def create_task_details_embed(
    task,
) -> discord.Embed:

    priority = task["priority"]

    embed = discord.Embed(
        title=(
            f"{PRIORITY_EMOJIS.get(priority, '📋')} "
            f"{task['title']}"
        ),
        color=EMBED_COLOR,
    )

    if task["description"]:

        embed.add_field(
            name="📝 Description",
            value=task["description"][:1024],
            inline=False,
        )

    embed.add_field(
        name="🎯 Priority",
        value=(
            f"{PRIORITY_EMOJIS.get(priority, '📋')} "
            f"{PRIORITY_LABELS.get(priority, priority.title())}"
        ),
        inline=True,
    )

    embed.add_field(
        name="📌 Status",
        value=task["status"].title(),
        inline=True,
    )

    embed.add_field(
        name="👤 Assigned To",
        value=task_assignee(task),
        inline=True,
    )

    embed.add_field(
        name="👨‍💻 Created By",
        value=f"<@{task['created_by']}>",
        inline=True,
    )

    if task["due_at"]:

        due_text = discord_timestamp(
            task["due_at"],
            "F",
        )

        if is_overdue(task):

            due_text = (
                "🚨 **OVERDUE**\n"
                f"{due_text}\n"
                f"{discord_timestamp(task['due_at'])}"
            )

        else:

            due_text += (
                f"\n{discord_timestamp(task['due_at'])}"
            )

        embed.add_field(
            name="📅 Due",
            value=due_text,
            inline=True,
        )

    else:

        embed.add_field(
            name="📅 Due",
            value="*No due date*",
            inline=True,
        )

    embed.add_field(
        name="🕐 Created",
        value=discord_timestamp(
            task["created_at"]
        ),
        inline=True,
    )

    if task["completed_at"]:

        embed.add_field(
            name="✅ Completed",
            value=(
                f"<@{task['completed_by']}>\n"
                f"{discord_timestamp(task['completed_at'])}"
            ),
            inline=False,
        )

    if task["deleted_at"]:

        embed.add_field(
            name="🗑️ Deleted",
            value=(
                f"<@{task['deleted_by']}>\n"
                f"{discord_timestamp(task['deleted_at'])}"
            ),
            inline=False,
        )

    return embed


# =========================================================
# TASK SELECT
# =========================================================

class TaskSelect(
    discord.ui.Select
):

    def __init__(
        self,
        tasks,
        action: str,
        cog,
    ):

        self.action = action
        self.cog = cog

        options = []

        for task in tasks:

            priority = task["priority"]

            label = task["title"][:100]

            description = (
                f"{PRIORITY_LABELS.get(priority, priority.title())}"
            )

            if is_overdue(task):

                description = (
                    "🚨 OVERDUE • "
                    + description
                )

            options.append(
                discord.SelectOption(
                    label=label,
                    description=description[:100],
                    value=str(task["id"]),
                    emoji=PRIORITY_EMOJIS.get(
                        priority,
                        "📋",
                    ),
                )
            )

        super().__init__(
            placeholder="Select a task...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ):

        task_id = int(
            self.values[0]
        )

        task = await database.get_task(
            str(interaction.guild_id),
            task_id,
        )

        if not task:

            await interaction.response.send_message(
                "❌ That task no longer exists.",
                ephemeral=True,
            )

            return

        # =================================================
        # COMPLETE
        # =================================================

        if self.action == "complete":

            result = await database.complete_task(
                str(interaction.guild_id),
                task_id,
                str(interaction.user.id),
            )

            if not result:

                await interaction.response.send_message(
                    "❌ That task has already been completed "
                    "or deleted.",
                    ephemeral=True,
                )

                return

            await interaction.response.send_message(
                (
                    f"✅ **{task['title']}**\n"
                    "Task marked as completed."
                ),
                ephemeral=True,
            )

            await self.cog.refresh_board(
                interaction.guild
            )

            return

        # =================================================
        # DELETE
        # =================================================

        if self.action == "delete":

            result = await database.delete_task(
                str(interaction.guild_id),
                task_id,
                str(interaction.user.id),
            )

            if not result:

                await interaction.response.send_message(
                    "❌ That task has already been "
                    "completed or deleted.",
                    ephemeral=True,
                )

                return

            await interaction.response.send_message(
                (
                    f"🗑️ **{task['title']}**\n"
                    "Task removed from the active board."
                ),
                ephemeral=True,
            )

            await self.cog.refresh_board(
                interaction.guild
            )

            return

        # =================================================
        # DETAILS
        # =================================================

        if self.action == "details":

            embed = create_task_details_embed(
                task
            )

            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
            )

            return

        # =================================================
        # EDIT
        # =================================================

        if self.action == "edit":

            await interaction.response.send_modal(
                EditTaskModal(
                    self.cog,
                    task,
                )
            )


# =========================================================
# TASK SELECT VIEW
# =========================================================

class TaskSelectView(
    discord.ui.View
):

    def __init__(
        self,
        tasks,
        action: str,
        cog,
    ):

        super().__init__(
            timeout=120
        )

        self.tasks = list(tasks)
        self.action = action
        self.cog = cog
        self.page = 0

        self.per_page = 25

        self._build()

    @property
    def total_pages(self):

        return max(
            1,
            (
                len(self.tasks)
                + self.per_page
                - 1
            )
            // self.per_page,
        )

    def _build(self):

        self.clear_items()

        start = (
            self.page
            * self.per_page
        )

        end = start + self.per_page

        page_tasks = self.tasks[
            start:end
        ]

        if page_tasks:

            self.add_item(
                TaskSelect(
                    page_tasks,
                    self.action,
                    self.cog,
                )
            )

        previous = discord.ui.Button(
            label="Previous",
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            disabled=self.page <= 0,
        )

        next_button = discord.ui.Button(
            label="Next",
            emoji="▶️",
            style=discord.ButtonStyle.secondary,
            disabled=(
                self.page
                >= self.total_pages - 1
            ),
        )

        async def previous_callback(
            interaction: discord.Interaction,
        ):

            self.page -= 1

            self._build()

            await interaction.response.edit_message(
                view=self
            )

        async def next_callback(
            interaction: discord.Interaction,
        ):

            self.page += 1

            self._build()

            await interaction.response.edit_message(
                view=self
            )

        previous.callback = previous_callback
        next_button.callback = next_callback

        self.add_item(
            previous
        )

        self.add_item(
            next_button
        )


# =========================================================
# HISTORY VIEW
# =========================================================

class HistoryView(
    discord.ui.View
):

    def __init__(
        self,
        tasks,
    ):

        super().__init__(
            timeout=120
        )

        self.tasks = list(tasks)

        self.page = 0

        self.per_page = 5

        self._build()

    @property
    def total_pages(self):

        return max(
            1,
            (
                len(self.tasks)
                + self.per_page
                - 1
            )
            // self.per_page,
        )

    def build_embed(self):

        embed = discord.Embed(
            title="📚 TO-DO HISTORY",
            description=(
                "Completed and deleted staff tasks."
            ),
            color=EMBED_COLOR,
        )

        start = (
            self.page
            * self.per_page
        )

        end = start + self.per_page

        page_tasks = self.tasks[
            start:end
        ]

        if not page_tasks:

            embed.description += (
                "\n\n📭 No task history."
            )

            return embed

        for task in page_tasks:

            if task["status"] == "completed":

                icon = "✅"

                action = (
                    f"Completed by <@{task['completed_by']}>"
                )

                when = task["completed_at"]

            else:

                icon = "🗑️"

                action = (
                    f"Deleted by <@{task['deleted_by']}>"
                )

                when = task["deleted_at"]

            value = (
                f"{action} "
                f"{discord_timestamp(when)}"
            )

            embed.add_field(
                name=(
                    f"{icon} "
                    f"{task['title'][:100]}"
                ),
                value=value,
                inline=False,
            )

        embed.set_footer(
            text=(
                f"Page {self.page + 1} "
                f"of {self.total_pages}"
            )
        )

        return embed

    def _build(self):

        self.clear_items()

        previous = discord.ui.Button(
            label="Previous",
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            disabled=self.page <= 0,
        )

        next_button = discord.ui.Button(
            label="Next",
            emoji="▶️",
            style=discord.ButtonStyle.secondary,
            disabled=(
                self.page
                >= self.total_pages - 1
            ),
        )

        async def previous_callback(
            interaction: discord.Interaction,
        ):

            self.page -= 1

            self._build()

            await interaction.response.edit_message(
                embed=self.build_embed(),
                view=self,
            )

        async def next_callback(
            interaction: discord.Interaction,
        ):

            self.page += 1

            self._build()

            await interaction.response.edit_message(
                embed=self.build_embed(),
                view=self,
            )

        previous.callback = previous_callback
        next_button.callback = next_callback

        self.add_item(previous)
        self.add_item(next_button)


# =========================================================
# MAIN TODO VIEW
# =========================================================

class TodoView(
    discord.ui.View
):

    def __init__(
        self,
        cog,
    ):

        super().__init__(
            timeout=None
        )

        self.cog = cog

    # =====================================================
    # ADD
    # =====================================================

    @discord.ui.button(
        label="Add Task",
        emoji="➕",
        style=discord.ButtonStyle.success,
        custom_id="todo:add",
        row=0,
    )
    async def add_task(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        await interaction.response.send_modal(
            AddTaskModal(
                self.cog
            )
        )

    # =====================================================
    # MANAGE / EDIT
    # =====================================================

    @discord.ui.button(
        label="Edit Task",
        emoji="✏️",
        style=discord.ButtonStyle.primary,
        custom_id="todo:edit",
        row=0,
    )
    async def edit_task(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        tasks = await database.get_open_tasks(
            str(interaction.guild_id)
        )

        if not tasks:

            await interaction.response.send_message(
                "📋 There are no open tasks.",
                ephemeral=True,
            )

            return

        await interaction.response.send_message(
            "✏️ Select the task you want to edit:",
            view=TaskSelectView(
                tasks,
                "edit",
                self.cog,
            ),
            ephemeral=True,
        )

    # =====================================================
    # COMPLETE
    # =====================================================

    @discord.ui.button(
        label="Complete",
        emoji="✅",
        style=discord.ButtonStyle.primary,
        custom_id="todo:complete",
        row=0,
    )
    async def complete_task(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        tasks = await database.get_open_tasks(
            str(interaction.guild_id)
        )

        if not tasks:

            await interaction.response.send_message(
                "📋 There are no open tasks.",
                ephemeral=True,
            )

            return

        await interaction.response.send_message(
            "✅ Select the task to complete:",
            view=TaskSelectView(
                tasks,
                "complete",
                self.cog,
            ),
            ephemeral=True,
        )

    # =====================================================
    # DELETE
    # =====================================================

    @discord.ui.button(
        label="Delete",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
        custom_id="todo:delete",
        row=1,
    )
    async def delete_task(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        tasks = await database.get_open_tasks(
            str(interaction.guild_id)
        )

        if not tasks:

            await interaction.response.send_message(
                "📋 There are no open tasks.",
                ephemeral=True,
            )

            return

        await interaction.response.send_message(
            "🗑️ Select the task to delete:",
            view=TaskSelectView(
                tasks,
                "delete",
                self.cog,
            ),
            ephemeral=True,
        )

    # =====================================================
    # DETAILS
    # =====================================================

    @discord.ui.button(
        label="Details",
        emoji="🔎",
        style=discord.ButtonStyle.secondary,
        custom_id="todo:details",
        row=1,
    )
    async def details(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        tasks = await database.get_open_tasks(
            str(interaction.guild_id)
        )

        if not tasks:

            await interaction.response.send_message(
                "📋 There are no open tasks.",
                ephemeral=True,
            )

            return

        await interaction.response.send_message(
            "🔎 Select a task:",
            view=TaskSelectView(
                tasks,
                "details",
                self.cog,
            ),
            ephemeral=True,
        )

    # =====================================================
    # REFRESH
    # =====================================================

    @discord.ui.button(
        label="Refresh",
        emoji="🔄",
        style=discord.ButtonStyle.secondary,
        custom_id="todo:refresh",
        row=2,
    )
    async def refresh(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        success = await self.cog.refresh_board(
            interaction.guild
        )

        if success:

            message = (
                "🔄 To-Do board refreshed."
            )

        else:

            message = (
                "⚠️ I couldn't refresh the board."
            )

        await interaction.followup.send(
            message,
            ephemeral=True,
        )

    # =====================================================
    # HISTORY
    # =====================================================

    @discord.ui.button(
        label="History",
        emoji="📚",
        style=discord.ButtonStyle.secondary,
        custom_id="todo:history",
        row=2,
    )
    async def history(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        tasks = await database.get_task_history(
            str(interaction.guild_id)
        )

        view = HistoryView(
            tasks
        )

        await interaction.response.send_message(
            embed=view.build_embed(),
            view=view,
            ephemeral=True,
        )
