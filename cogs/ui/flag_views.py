from __future__ import annotations

import asyncio
import hashlib
import logging

import discord
from discord.ext import commands

from cogs import utils

log = logging.getLogger("dayz-manager")


class FlagManageView(discord.ui.LayoutView):
    """Persistent Components V2 dashboard for one flag session."""

    _locks: dict[str, asyncio.Lock] = {}

    def __init__(
        self,
        guild: discord.Guild | None,
        map_key: str,
        server: str,
        bot: commands.Bot,
        rows,
    ):
        super().__init__(timeout=None)
        self.guild = guild
        self.bot = bot
        self.map_key = utils.normalize_map(map_key)
        self.server = utils.normalize_server(server)
        self.rows = list(rows)

        guild_key = str(guild.id) if guild else "global"
        raw = f"{guild_key}:{self.map_key}:{self.server}"
        self.identifier = hashlib.sha1(raw.encode()).hexdigest()[:16]

        self._build_dashboard()

    @classmethod
    async def create(
        cls,
        guild: discord.Guild | None,
        map_key: str,
        server: str,
        bot: commands.Bot,
    ) -> "FlagManageView":
        rows = []
        if guild is not None:
            rows = await utils.get_all_flags(str(guild.id), map_key, server)
        return cls(guild, map_key, server, bot, rows)

    @property
    def session_key(self) -> str:
        return f"{self.guild.id if self.guild else 'global'}:{self.map_key}:{self.server}"

    def get_lock(self) -> asyncio.Lock:
        lock = self._locks.get(self.session_key)
        if lock is None:
            lock = self._locks[self.session_key] = asyncio.Lock()
        return lock

    def _build_dashboard(self) -> None:
        map_info = utils.MAP_DATA.get(
            self.map_key,
            {"name": self.map_key.title(), "image": None},
        )
        rows = sorted(self.rows, key=lambda row: str(row["flag"]).casefold())
        claimed = [row for row in rows if row["role_id"] or row["status"] == "❌"]
        available = [row for row in rows if not (row["role_id"] or row["status"] == "❌")]
        total = len(rows)
        pct = round((len(claimed) / total) * 100) if total else 0

        header = discord.ui.TextDisplay(
            f"# 🚩 DayZ Manager — Flag System\n"
            f"### {map_info['name']} • {self.server}\n"
            "Claim, release, search, and review faction flags from one live control panel."
        )

        stats_text = discord.ui.TextDisplay(
            f"## Live Status\n"
            f"🟢 **{len(available)} Available**   •   🔴 **{len(claimed)} Claimed**   •   "
            f"🏴 **{total} Total**\n"
            f"`{'■' * min(10, round(pct / 10))}{'□' * max(0, 10 - round(pct / 10))}` **{pct}% claimed**"
        )

        image = map_info.get("image")
        if image:
            stats_component = discord.ui.Section(
                stats_text,
                accessory=discord.ui.Thumbnail(image, description=f"{map_info['name']} map"),
            )
        else:
            stats_component = stats_text

        # Keep the public dashboard useful at a glance: players can immediately
        # see both what is available and what has already been claimed.
        if available:
            available_lines = [f"🟢 **{row['flag']}**" for row in available]
            available_registry = discord.ui.TextDisplay(
                "## Available Flags\n" + "\n".join(available_lines)
            )
        else:
            available_registry = discord.ui.TextDisplay(
                "## Available Flags\n🔴 No flags are currently available."
            )

        if claimed:
            claimed_lines = []
            for row in claimed:
                owner = f"<@&{row['role_id']}>" if row["role_id"] else "Assigned"
                claimed_lines.append(f"🔴 **{row['flag']}** → {owner}")
            claimed_registry = discord.ui.TextDisplay(
                "## Claimed Flags\n" + "\n".join(claimed_lines)
            )
        else:
            claimed_registry = discord.ui.TextDisplay(
                "## Claimed Flags\n🟢 No flags are currently claimed."
            )

        primary_row = discord.ui.ActionRow(
            DashboardButton("Claim Flag", "🟢", discord.ButtonStyle.success, f"flag_claim:{self.identifier}", "claim"),
            DashboardButton("Release Flag", "🔴", discord.ButtonStyle.danger, f"flag_release:{self.identifier}", "release"),
            DashboardButton("View Flags", "📋", discord.ButtonStyle.primary, f"flag_view:{self.identifier}", "view"),
        )

        secondary_row = discord.ui.ActionRow(
            DashboardButton("Find Flag", "🔎", discord.ButtonStyle.secondary, f"flag_find:{self.identifier}", "find"),
            DashboardButton("History", "🕘", discord.ButtonStyle.secondary, f"flag_history:{self.identifier}", "history"),
            DashboardButton("Admin Panel", "⚙️", discord.ButtonStyle.secondary, f"flag_admin:{self.identifier}", "admin"),
        )

        footer = discord.ui.TextDisplay(
            "-# DayZ Manager • Live Flag Management • Updates automatically after every claim/release"
        )

        container = discord.ui.Container(
            header,
            discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
            stats_component,
            discord.ui.Separator(),
            available_registry,
            discord.ui.Separator(),
            claimed_registry,
            discord.ui.Separator(),
            primary_row,
            secondary_row,
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            footer,
            accent_colour=utils.EMBED_COLOR,
        )
        self.add_item(container)

    async def refresh_message(self) -> None:
        if not self.guild:
            return
        row = await utils.get_flag_message(str(self.guild.id), self.map_key, self.server)
        if not row:
            return
        channel = self.guild.get_channel(int(row["channel_id"]))
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            message = await channel.fetch_message(int(row["message_id"]))
            new_view = await FlagManageView.create(self.guild, self.map_key, self.server, self.bot)
            if getattr(message.flags, "components_v2", False):
                await message.edit(view=new_view)
                try:
                    self.bot.add_view(new_view, message_id=message.id)
                except ValueError:
                    pass
            else:
                await migrate_message_to_v2(message, channel, new_view, self.guild, self.map_key, self.server, self.bot)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            log.exception("Failed refreshing Components V2 flag dashboard.")

    async def assign_flag(self, interaction: discord.Interaction) -> None:
        if not self.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("🚫 Server only.", ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "🚫 Administrator permission required.", ephemeral=True
            )
        lock = self.get_lock()
        if lock.locked():
            return await interaction.response.send_message("⚠️ Another flag action is in progress.", ephemeral=True)

        async with lock:
            await interaction.response.defer(ephemeral=True)
            flags = await utils.get_all_flags(str(self.guild.id), self.map_key, self.server)
            available = [row for row in flags if row["status"] == "✅" and row["role_id"] is None]
            if not available:
                return await interaction.followup.send("⚠️ No unclaimed flags are available.", ephemeral=True)

            options = [discord.SelectOption(label=f"🟢 {row['flag']}", value=row["flag"]) for row in available[:25]]
            select = discord.ui.Select(placeholder="Choose an available flag", options=options)
            view = discord.ui.View(timeout=90)
            view.add_item(select)

            async def flag_cb(inter: discord.Interaction):
                if not isinstance(inter.user, discord.Member) or not inter.user.guild_permissions.administrator:
                    return await inter.response.send_message(
                        "🚫 Administrator permission required.", ephemeral=True
                    )
                flag = select.values[0]
                role_select = discord.ui.RoleSelect(placeholder=f"Choose the faction role for {flag}")
                role_view = discord.ui.View(timeout=90)
                role_view.add_item(role_select)

                async def role_cb(inter2: discord.Interaction):
                    if not isinstance(inter2.user, discord.Member) or not inter2.user.guild_permissions.administrator:
                        return await inter2.response.send_message(
                            "🚫 Administrator permission required.", ephemeral=True
                        )
                    selected = role_select.values[0]
                    role = self.guild.get_role(selected.id)
                    if not role or role.is_default() or role.managed:
                        return await inter2.response.edit_message(content="⚠️ That role cannot own a flag.", view=None)
                    result = await utils.claim_flag(
                        str(self.guild.id), self.map_key, self.server, flag, str(role.id),
                        actor_id=str(inter2.user.id), source="dashboard:claim",
                    )
                    if not result:
                        return await inter2.response.edit_message(content="⚠️ That flag is no longer available.", view=None)
                    await self.refresh_message()
                    await inter2.response.edit_message(
                        content=f"✅ **{flag}** is now assigned to {role.mention}.", view=None
                    )

                role_select.callback = role_cb
                await inter.response.edit_message(content=f"### 🏴 {flag}\nChoose the role that will own this flag.", view=role_view)

            select.callback = flag_cb
            await interaction.followup.send(
                f"### 🟢 Claim a Flag\n**{self.map_key.title()} • {self.server}**\nChoose an available flag below.",
                view=view, ephemeral=True,
            )

    async def release_flag(self, interaction: discord.Interaction) -> None:
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("🚫 Administrator permission required.", ephemeral=True)
        if not self.guild:
            return
        lock = self.get_lock()
        if lock.locked():
            return await interaction.response.send_message("⚠️ Another flag action is in progress.", ephemeral=True)
        async with lock:
            await interaction.response.defer(ephemeral=True)
            flags = await utils.get_all_flags(str(self.guild.id), self.map_key, self.server)
            claimed = [row for row in flags if row["status"] == "❌" and row["role_id"]]
            if not claimed:
                return await interaction.followup.send("⚠️ No flags are currently claimed.", ephemeral=True)
            options = [discord.SelectOption(label=f"🔴 {row['flag']}", value=row["flag"]) for row in claimed[:25]]
            select = discord.ui.Select(placeholder="Choose a claimed flag to release", options=options)
            view = discord.ui.View(timeout=90)
            view.add_item(select)

            async def callback(inter: discord.Interaction):
                if not isinstance(inter.user, discord.Member) or not inter.user.guild_permissions.administrator:
                    return await inter.response.send_message(
                        "🚫 Administrator permission required.", ephemeral=True
                    )
                flag = select.values[0]
                result = await utils.release_flag(
                    str(self.guild.id), self.map_key, self.server, flag,
                    actor_id=str(inter.user.id), source="dashboard:release",
                )
                if not result:
                    return await inter.response.edit_message(content="⚠️ That flag is already available.", view=None)
                await self.refresh_message()
                await inter.response.edit_message(content=f"✅ **{flag}** has been released.", view=None)

            select.callback = callback
            await interaction.followup.send(
                f"### 🔴 Release a Flag\n**{self.map_key.title()} • {self.server}**\nChoose a claimed flag below.",
                view=view, ephemeral=True,
            )

    async def view_flags(self, interaction: discord.Interaction) -> None:
        if not self.guild:
            return
        rows = await utils.get_all_flags(str(self.guild.id), self.map_key, self.server)
        claimed = []
        available = []
        for row in sorted(rows, key=lambda r: str(r["flag"]).casefold()):
            if row["role_id"] or row["status"] == "❌":
                owner = f"<@&{row['role_id']}>" if row["role_id"] else "Assigned"
                claimed.append(f"🔴 **{row['flag']}** — {owner}")
            else:
                available.append(f"🟢 **{row['flag']}**")
        text = (
            f"# 📋 Flag Registry\n### {self.map_key.title()} • {self.server}\n\n"
            f"## 🔴 Claimed ({len(claimed)})\n" + ("\n".join(claimed) if claimed else "*None*") +
            f"\n\n## 🟢 Available ({len(available)})\n" + ("\n".join(available) if available else "*None*")
        )
        await interaction.response.send_message(text[:3900], ephemeral=True)

    async def show_history(self, interaction: discord.Interaction) -> None:
        if not self.guild:
            return
        rows = await utils.get_flag_history(str(self.guild.id), self.map_key, self.server, 10)
        if not rows:
            return await interaction.response.send_message("🕘 No flag activity has been recorded yet.", ephemeral=True)
        lines = []
        for row in rows:
            action = "claimed" if row["action"] == "claim" else "released"
            actor = f"<@{row['actor_id']}>" if row["actor_id"] else "Unknown"
            role = f" <@&{row['role_id']}>" if row["role_id"] else ""
            ts = int(row["created_at"].timestamp())
            lines.append(f"• **{row['flag']}** {action}{role} by {actor} • <t:{ts}:R>")
        await interaction.response.send_message(
            f"# 🕘 Recent Flag Activity\n### {self.map_key.title()} • {self.server}\n\n" + "\n".join(lines),
            ephemeral=True,
        )

    async def find_flag(self, interaction: discord.Interaction) -> None:
        if not self.guild:
            return
        modal = FlagSearchModal(self)
        await interaction.response.send_modal(modal)

    async def admin_panel(self, interaction: discord.Interaction) -> None:
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("🚫 Administrator permission required.", ephemeral=True)
        if not self.guild:
            return
        rows = await utils.get_all_flags(str(self.guild.id), self.map_key, self.server)
        claimed = sum(1 for row in rows if row["role_id"] or row["status"] == "❌")
        stored = await utils.get_flag_message(str(self.guild.id), self.map_key, self.server)
        status = "✅ Stored" if stored else "⚠️ Missing storage record"
        view = AdminQuickView(self)
        await interaction.response.send_message(
            f"# ⚙️ Flag Admin Panel\n### {self.map_key.title()} • {self.server}\n\n"
            f"🏴 **Flags:** {len(rows)} total • {claimed} claimed • {len(rows)-claimed} available\n"
            f"💾 **Dashboard:** {status}\n\n"
            "Use the buttons below for quick actions. Full setup deletion remains available through `/deletesetup`.",
            view=view, ephemeral=True,
        )


class DashboardButton(discord.ui.Button):
    def __init__(self, label: str, emoji: str, style: discord.ButtonStyle, custom_id: str, action: str):
        super().__init__(label=label, emoji=emoji, style=style, custom_id=custom_id)
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, FlagManageView):
            return
        actions = {
            "claim": view.assign_flag,
            "release": view.release_flag,
            "view": view.view_flags,
            "find": view.find_flag,
            "history": view.show_history,
            "admin": view.admin_panel,
        }
        callback = actions.get(self.action)
        if callback:
            await callback(interaction)


class FlagSearchModal(discord.ui.Modal, title="Find a Flag"):
    query = discord.ui.TextInput(
        label="Flag name",
        placeholder="Example: Wolf, NAPA, Bear...",
        min_length=1,
        max_length=30,
    )

    def __init__(self, dashboard: FlagManageView):
        super().__init__(timeout=120)
        self.dashboard = dashboard

    async def on_submit(self, interaction: discord.Interaction) -> None:
        guild = self.dashboard.guild
        if not guild:
            return await interaction.response.send_message("🚫 Server only.", ephemeral=True)
        value = str(self.query.value).strip().casefold()
        rows = await utils.get_all_flags(str(guild.id), self.dashboard.map_key, self.dashboard.server)
        matches = [row for row in rows if value in str(row["flag"]).casefold()]
        if not matches:
            return await interaction.response.send_message(f"🔎 No flag matched **{self.query.value}**.", ephemeral=True)
        lines = []
        for row in matches[:10]:
            if row["role_id"] or row["status"] == "❌":
                owner = f"<@&{row['role_id']}>" if row["role_id"] else "Assigned"
                lines.append(f"🔴 **{row['flag']}** — Claimed by {owner}")
            else:
                lines.append(f"🟢 **{row['flag']}** — Available")
        await interaction.response.send_message("# 🔎 Flag Search\n" + "\n".join(lines), ephemeral=True)


class AdminQuickView(discord.ui.View):
    def __init__(self, dashboard: FlagManageView):
        super().__init__(timeout=120)
        self.dashboard = dashboard

    @discord.ui.button(label="Refresh Dashboard", emoji="🔄", style=discord.ButtonStyle.primary)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self.dashboard.refresh_message()
        await interaction.followup.send("✅ Dashboard refreshed.", ephemeral=True)

    @discord.ui.button(label="Recent History", emoji="🕘", style=discord.ButtonStyle.secondary)
    async def history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.dashboard.show_history(interaction)


async def migrate_message_to_v2(
    message: discord.Message,
    channel: discord.TextChannel,
    view: FlagManageView,
    guild: discord.Guild,
    map_key: str,
    server: str,
    bot: commands.Bot,
) -> discord.Message:
    """Replace an old classic embed board with a Components V2 dashboard."""
    try:
        await message.delete()
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        pass

    new_message = await channel.send(view=view)
    await utils.save_flag_message(
        str(guild.id), map_key, server, str(channel.id), str(new_message.id)
    )
    try:
        bot.add_view(view, message_id=new_message.id)
    except ValueError:
        pass
    return new_message