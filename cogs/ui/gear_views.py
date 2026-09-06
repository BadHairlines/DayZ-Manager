from __future__ import annotations

import asyncio
import hashlib

import discord
from discord.ext import commands

from cogs import utils


class GearManageView(discord.ui.LayoutView):
    """Persistent Components V2 dashboard for raincoat/armband claim systems."""

    _locks: dict[str, asyncio.Lock] = {}

    def __init__(self, guild, map_key, server, system_type, bot, rows):
        super().__init__(timeout=None)
        self.guild = guild
        self.map_key = utils.normalize_map(map_key)
        self.server = utils.normalize_server(server)
        self.system_type = utils.normalize_system_type(system_type)
        self.bot = bot
        self.rows = list(rows)

        guild_key = str(guild.id) if guild else "global"
        raw = f"{guild_key}:{self.map_key}:{self.server}:{self.system_type}"
        self.identifier = hashlib.sha1(raw.encode()).hexdigest()[:16]
        self._build_dashboard()

    @classmethod
    async def create(cls, guild, map_key, server, system_type, bot):
        rows = []
        if guild is not None:
            rows = await utils.get_claim_system_items(
                str(guild.id), map_key, server, system_type
            )
        return cls(guild,map_key,server,system_type,bot,rows)

    @property
    def session_key(self):
        return f"{self.guild.id if self.guild else 'global'}:{self.map_key}:{self.server}:{self.system_type}"

    def get_lock(self):
        if self.session_key not in self._locks:
            self._locks[self.session_key] = asyncio.Lock()
        return self._locks[self.session_key]

    def _build_dashboard(self):
        info = utils.CLAIM_SYSTEMS[self.system_type]
        map_info = utils.MAP_DATA.get(self.map_key, {"name":self.map_key.title(),"image":None})
        rows = sorted(self.rows,key=lambda r:str(r["flag"]).casefold())
        claimed = [r for r in rows if r["role_id"] or r["status"]=="❌"]
        available = [r for r in rows if not (r["role_id"] or r["status"]=="❌")]
        total=len(rows)
        pct=round(len(claimed)/total*100) if total else 0

        header=discord.ui.TextDisplay(
            f"# {info['emoji']} DayZ Manager — {info['name']}\n"
            f"### {map_info['name']} • {self.server}\n"
            f"Assign and release {info['name'].lower()} for faction identification."
        )
        stats=discord.ui.TextDisplay(
            f"## Live Status\n🟢 **{len(available)} Available**   •   "
            f"🔴 **{len(claimed)} Claimed**   •   **{total} Total**\n"
            f"`{'■'*min(10,round(pct/10))}{'□'*max(0,10-round(pct/10))}` **{pct}% claimed**"
        )

        available_text = (
            "## Available\n" + "\n".join(f"🟢 **{r['flag']}**" for r in available)
            if available else "## Available\n🔴 None currently available."
        )
        claimed_lines=[]
        for r in claimed:
            owner=f"<@&{r['role_id']}>" if r["role_id"] else "Assigned"
            claimed_lines.append(f"🔴 **{r['flag']}** → {owner}")
        claimed_text = (
            "## Claimed\n" + "\n".join(claimed_lines)
            if claimed_lines else "## Claimed\n🟢 None currently claimed."
        )

        actions=[
            GearButton("Assign","🟢",discord.ButtonStyle.success,f"gear_assign:{self.identifier}","assign"),
            GearButton("Release","🔴",discord.ButtonStyle.danger,f"gear_release:{self.identifier}","release"),
        ]
        if self.guild:
            from webapp import claim_system_page_url
            url=claim_system_page_url(
                self.guild.id,self.system_type,self.map_key,self.server
            )
            if url:
                actions.append(discord.ui.Button(
                    label="Live Website",emoji="🌐",
                    style=discord.ButtonStyle.link,url=url
                ))

        container=discord.ui.Container(
            header,discord.ui.Separator(),
            stats,discord.ui.Separator(),
            discord.ui.TextDisplay(available_text),discord.ui.Separator(),
            discord.ui.TextDisplay(claimed_text),discord.ui.Separator(),
            discord.ui.ActionRow(*actions),
            discord.ui.TextDisplay(
                f"-# DayZ Manager • {info['name']} Claim System • Updates automatically"
            ),
            accent_colour=utils.EMBED_COLOR,
        )
        self.add_item(container)

    async def refresh_message(self):
        if not self.guild: return
        stored=await utils.get_claim_system_message(
            str(self.guild.id),self.map_key,self.server,self.system_type
        )
        if not stored: return
        channel=self.guild.get_channel(int(stored["channel_id"]))
        if not isinstance(channel,discord.TextChannel): return
        try:
            msg=await channel.fetch_message(int(stored["message_id"]))
            view=await GearManageView.create(
                self.guild,self.map_key,self.server,self.system_type,self.bot
            )
            await msg.edit(view=view)
            try:self.bot.add_view(view,message_id=msg.id)
            except ValueError:pass
        except (discord.NotFound,discord.Forbidden,discord.HTTPException):
            return

    async def assign_item(self,interaction):
        if not self.guild or not isinstance(interaction.user,discord.Member):
            return await interaction.response.send_message("🚫 Server only.",ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "🚫 Administrator permission required.",ephemeral=True
            )
        async with self.get_lock():
            await interaction.response.defer(ephemeral=True)
            rows=await utils.get_claim_system_items(
                str(self.guild.id),self.map_key,self.server,self.system_type
            )
            available=[r for r in rows if r["status"]=="✅" and r["role_id"] is None]
            if not available:
                return await interaction.followup.send("⚠️ Nothing is available.",ephemeral=True)
            select=discord.ui.Select(
                placeholder="Choose an available option",
                options=[discord.SelectOption(label=f"🟢 {r['flag']}",value=r["flag"]) for r in available[:25]]
            )
            view=discord.ui.View(timeout=90);view.add_item(select)

            async def item_cb(inter):
                if not isinstance(inter.user,discord.Member) or not inter.user.guild_permissions.administrator:
                    return await inter.response.send_message("🚫 Administrator permission required.",ephemeral=True)
                item=select.values[0]
                roles=discord.ui.RoleSelect(placeholder=f"Choose the faction role for {item}")
                role_view=discord.ui.View(timeout=90);role_view.add_item(roles)
                async def role_cb(inter2):
                    role=self.guild.get_role(roles.values[0].id)
                    if not role or role.is_default() or role.managed:
                        return await inter2.response.edit_message(content="⚠️ That role cannot own this option.",view=None)
                    ok=await utils.claim_system_item(
                        str(self.guild.id),self.map_key,self.server,self.system_type,
                        item,str(role.id),actor_id=str(inter2.user.id),source="dashboard:assign"
                    )
                    if not ok:
                        return await inter2.response.edit_message(content="⚠️ That option is no longer available.",view=None)
                    await self.refresh_message()
                    await inter2.response.edit_message(content=f"✅ **{item}** assigned to {role.mention}.",view=None)
                roles.callback=role_cb
                await inter.response.edit_message(content=f"### Assign {item}\nChoose the faction role.",view=role_view)
            select.callback=item_cb
            await interaction.followup.send("### 🟢 Assign\nChoose an available option.",view=view,ephemeral=True)

    async def release_item(self,interaction):
        if not isinstance(interaction.user,discord.Member) or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("🚫 Administrator permission required.",ephemeral=True)
        async with self.get_lock():
            await interaction.response.defer(ephemeral=True)
            rows=await utils.get_claim_system_items(
                str(self.guild.id),self.map_key,self.server,self.system_type
            )
            claimed=[r for r in rows if r["role_id"]]
            if not claimed:
                return await interaction.followup.send("⚠️ Nothing is currently claimed.",ephemeral=True)
            select=discord.ui.Select(
                placeholder="Choose a claimed option",
                options=[discord.SelectOption(label=f"🔴 {r['flag']}",value=r["flag"]) for r in claimed[:25]]
            )
            view=discord.ui.View(timeout=90);view.add_item(select)
            async def cb(inter):
                item=select.values[0]
                ok=await utils.release_system_item(
                    str(self.guild.id),self.map_key,self.server,self.system_type,
                    item,actor_id=str(inter.user.id),source="dashboard:release"
                )
                if not ok:
                    return await inter.response.edit_message(content="⚠️ Already available.",view=None)
                await self.refresh_message()
                await inter.response.edit_message(content=f"✅ **{item}** released.",view=None)
            select.callback=cb
            await interaction.followup.send("### 🔴 Release\nChoose a claimed option.",view=view,ephemeral=True)


class GearButton(discord.ui.Button):
    def __init__(self,label,emoji,style,custom_id,action):
        super().__init__(label=label,emoji=emoji,style=style,custom_id=custom_id)
        self.action=action
    async def callback(self,interaction):
        view=self.view
        if not isinstance(view,GearManageView): return
        if self.action=="assign": await view.assign_item(interaction)
        elif self.action=="release": await view.release_item(interaction)
