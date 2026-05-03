
Action: file_editor create /app/patched/cogs/ui_views.py --file-text "import asyncio
import logging

import discord
from discord.ext import commands
from discord.ui import View, button, Select, Button

from cogs import utils

log = logging.getLogger(\"dayz-manager\")

MAX_SELECT_OPTIONS = 25


class FlagManageView(View):
    \"\"\"Persistent flag control panel.\"\"\"

    _locks: dict[str, asyncio.Lock] = {}

    def __init__(self, guild: discord.Guild, map_key: str, bot: commands.Bot):
        super().__init__(timeout=None)
        self.guild = guild
        self.map_key = map_key
        self.bot = bot

    # -----------------------------
    # LOCKING
    # -----------------------------
    @property
    def session_key(self) -> str:
        return f\"{self.guild.id}:{self.map_key}\"

    def get_lock(self) -> asyncio.Lock:
        if self.session_key not in self._locks:
            self._locks[self.session_key] = asyncio.Lock()
        return self._locks[self.session_key]

    # -----------------------------
    # EMBED REFRESH
    # -----------------------------
    async def refresh_flag_embed(self):
        try:
            await utils.refresh_flag_message(
                self.bot,
                str(self.guild.id),
                self.map_key,
                view=self,
            )
        except Exception as e:
            log.warning(f\"Failed embed refresh: {e}\")

    # -----------------------------
    # ROLE OPTIONS
    # -----------------------------
    async def role_options(self):
        roles = [
            r for r in self.guild.roles
            if not r.is_default() and not r.managed
        ]
        roles.sort(key=lambda r: (-r.position, r.name.lower()))

        return [
            discord.SelectOption(label=r.name[:100], value=str(r.id))
            for r in roles[:MAX_SELECT_OPTIONS]
        ]

    # -----------------------------
    # CANCEL BUTTON (shared callback)
    # -----------------------------
    async def cancel(self, interaction: discord.Interaction):
        # ephemeral panel is an original response — edit it directly
        if interaction.response.is_done():
            await interaction.edit_original_response(content=\"❌ Cancelled.\", view=None)
        else:
            await interaction.response.edit_message(content=\"❌ Cancelled.\", view=None)

    def _cancel_button(self) -> Button:
        btn = Button(label=\"Cancel\", style=discord.ButtonStyle.secondary)
        btn.callback = self.cancel
        return btn

    # =========================================================
    # ASSIGN FLOW
    # =========================================================
    @button(label=\"🟩 Assign Flag\", style=discord.ButtonStyle.success, custom_id=\"assign_flag_btn\")
    async def assign_flag(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(\"🚫 Admins only.\", ephemeral=True)

        lock = self.get_lock()
        if lock.locked():
            return await interaction.response.send_message(
                \"⚠️ Another action is in progress. Please wait.\",
                ephemeral=True,
            )

        async with lock:
            await interaction.response.defer(ephemeral=True)

            guild_id = str(self.guild.id)
            flags = await utils.get_all_flags(guild_id, self.map_key)
            available = [f for f in flags if f[\"status\"] == \"✅\"]

            if not available:
                return await interaction.followup.send(\"⚠️ No unclaimed flags.\", ephemeral=True)

            options = [
                discord.SelectOption(label=f\"🟩 {f['flag']}\", value=f[\"flag\"])
                for f in available[:MAX_SELECT_OPTIONS]
            ]

            select = Select(placeholder=\"Select a flag\", options=options)
            view = View()
            view.add_item(select)
            view.add_item(self._cancel_button())

            async def on_select(inter: discord.Interaction):
                await inter.response.defer(ephemeral=True)
                flag = select.values[0]

                row = await utils.get_flag(guild_id, self.map_key, flag)
                if not row or row[\"status\"] != \"✅\":
                    return await inter.edit_original_response(
                        content=\"⚠️ Flag no longer available.\",
                        view=None,
                    )

                roles = await self.role_options()
                if not roles:
                    return await inter.edit_original_response(
                        content=\"⚠️ No roles available.\",
                        view=None,
                    )

                role_select = Select(placeholder=\"Assign role\", options=roles)
                step = View()
                step.add_item(role_select)
                step.add_item(self._cancel_button())

                async def on_role(inter2: discord.Interaction):
                    await inter2.response.defer(ephemeral=True)

                    role = self.guild.get_role(int(role_select.values[0]))
                    if not role:
                        return await inter2.edit_original_response(
                            content=\"⚠️ Role not found.\",
                            view=None,
                        )

                    await utils.set_flag(
                        guild_id,
                        self.map_key,
                        flag,
                        \"❌\",
                        str(role.id),
                    )

                    await self.refresh_flag_embed()

                    await inter2.edit_original_response(
                        content=f\"🏴 **{flag} → {role.mention}** assigned.\",
                        view=None,
                    )

                role_select.callback = on_role

                await inter.edit_original_response(
                    content=f\"Select role for **{flag}**\",
                    view=step,
                )

            select.callback = on_select

            await interaction.followup.send(\"Choose a flag:\", view=view, ephemeral=True)

    # =========================================================
    # RELEASE FLOW
    # =========================================================
    @button(label=\"🟥 Release Flag\", style=discord.ButtonStyle.danger, custom_id=\"release_flag_btn\")
    async def release_flag(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(\"🚫 Admins only.\", ephemeral=True)

        lock = self.get_lock()
        if lock.locked():
            return await interaction.response.send_message(
                \"⚠️ Another action is in progress. Please wait.\",
                ephemeral=True,
            )

        async with lock:
            await interaction.response.defer(ephemeral=True)

            guild_id = str(self.guild.id)
            flags = await utils.get_all_flags(guild_id, self.map_key)
            claimed = [f for f in flags if f[\"status\"] == \"❌\"]

            if not claimed:
                return await interaction.followup.send(\"⚠️ No claimed flags.\", ephemeral=True)

            options = [
                discord.SelectOption(label=f\"🟥 {f['flag']}\", value=f[\"flag\"])
                for f in claimed[:MAX_SELECT_OPTIONS]
            ]

            select = Select(placeholder=\"Select flag\", options=options)
            view = View()
            view.add_item(select)
            view.add_item(self._cancel_button())

            async def on_select(inter: discord.Interaction):
                await inter.response.defer(ephemeral=True)
                flag = select.values[0]

                row = await utils.get_flag(guild_id, self.map_key, flag)
                if not row or row[\"status\"] != \"❌\":
                    return await inter.edit_original_response(
                        content=\"⚠️ Already unclaimed.\",
                        view=None,
                    )

                await utils.release_flag(guild_id, self.map_key, flag)
                await self.refresh_flag_embed()

                await inter.edit_original_response(
                    content=f\"🏳️ **{flag} released**\",
                    view=None,
                )

            select.callback = on_select

            await interaction.followup.send(\"Choose a flag:\", view=view, ephemeral=True)
"
Observation: calling "initialize": sending "initialize": Bad Request
