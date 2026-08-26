from __future__ import annotations

from datetime import datetime

import discord

from . import database


# =========================================================
# COLORS / EMOJIS
# =========================================================

EMBED_COLOR = 0x3498DB

PRIORITY_EMOJIS = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
}


# =========================================================
# ADD TASK MODAL
# =========================================================

class AddTaskModal(discord.ui.Modal):

    def __init__(self, cog):

        super().__init__(
            title="Create New Task"
        )

        self.cog = cog

        self.title_input = discord.ui.TextInput(
            label="Task Name",
            placeholder="Enter the task name...",
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

        self.add_item(self.title_input)
        self.add_item(self.description_input)

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):

        await database.create_task(
            guild_id=str(interaction.guild_id),
            title=self.title_input.value.strip(),
            description=(
                self.description_input.value.strip()
                or None
            ),
            created_by=str(interaction.user.id),
            assigned_to=None,
            priority="medium",
            due_at=None,
        )

        await interaction.response.send_message(
            "✅ **Task created successfully.**",
            ephemeral=True,
        )

        await self.cog.refresh_board(
            interaction.guild
        )


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

        for task in tasks[:25]:

            priority = task["priority"]

            options.append(
                discord.SelectOption(
                    label=task["title"][:100],
                    description=(
                        f"{priority.title()} priority"
                    ),
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

        if self.action == "complete":

            result = await database.complete_task(
                str(interaction.guild_id),
                task_id,
                str(interaction.user.id),
            )

            if not result:

                await interaction.response.send_message(
                    "❌ That task has already been completed.",
                    ephemeral=True,
                )

                return

            await interaction.response.send_message(
                f"✅ **{task['title']}** marked as completed.",
                ephemeral=True,
            )

            await self.cog.refresh_board(
                interaction.guild
            )

        elif self.action == "delete":

            await database.delete_task(
                str(interaction.guild_id),
                task_id,
            )

            await interaction.response.send_message(
                f"🗑️ **{task['title']}** deleted.",
                ephemeral=True,
            )

            await self.cog.refresh_board(
                interaction.guild
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
            timeout=60
        )

        self.add_item(
            TaskSelect(
                tasks,
                action,
                cog,
            )
        )


# =========================================================
# MAIN TODO VIEW
# =========================================================

class TodoView(
    discord.ui.View
):

    def __init__(self, cog):

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

        if not self.cog.is_staff(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ You do not have permission to add tasks.",
                ephemeral=True,
            )

            return

        await interaction.response.send_modal(
            AddTaskModal(
                self.cog
            )
        )

    # =====================================================
    # COMPLETE
    # =====================================================

    @discord.ui.button(
        label="Complete Task",
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

        if not self.cog.is_staff(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ You do not have permission to complete tasks.",
                ephemeral=True,
            )

            return

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
            "Select the task you want to mark as completed:",
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
        label="Delete Task",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
        custom_id="todo:delete",
        row=0,
    )
    async def delete_task(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        if not self.cog.is_staff(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ You do not have permission to delete tasks.",
                ephemeral=True,
            )

            return

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
            "Select the task you want to delete:",
            view=TaskSelectView(
                tasks,
                "delete",
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
        row=0,
    )
    async def refresh(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        await self.cog.refresh_board(
            interaction.guild
        )

        await interaction.followup.send(
            "🔄 To-Do board refreshed.",
            ephemeral=True,
        )
