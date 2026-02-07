import discord
from discord import app_commands
from discord.ext import commands
import logging

from cogs import utils
from cogs.factions.faction_utils import ensure_faction_table

log = logging.getLogger("dayz-manager")

MAP_CHOICES = [
    app_commands.Choice(name="Livonia", value="Livonia"),
    app_commands.Choice(name="Chernarus", value="Chernarus"),
    app_commands.Choice(name="Sakhal", value="Sakhal"),
]

ITEMS_PER_PAGE = 5  # factions per page
MEMBERS_PER_FIELD = 15  # how many members to show per field chunk


class FactionList(commands.Cog):
    """Lists active factions for a guild."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def make_faction_fields(self, row, guild):
        """Return a list of fields for a faction, splitting large member lists."""
        faction_name = row["faction_name"]
        role_id = row["role_id"]
        leader_id = row["leader_id"]
        member_ids = list(row["member_ids"] or [])
        claimed_flag = row.get("claimed_flag") or "—"

        role = guild.get_role(int(role_id)) if role_id else None
        status = "✅" if role else "⚠️"
        role_mention = role.mention if role else "None"
        leader_mention = f"<@{leader_id}>" if leader_id else "Unknown"

        # Remove duplicates, keep leader first
        unique_members = [str(mid) for mid in member_ids if mid and str(mid) != str(leader_id)]
        total_members = len(unique_members) + (1 if leader_id else 0)

        # Split members into chunks
        member_chunks = [
            unique_members[i:i + MEMBERS_PER_FIELD]
            for i in range(0, len(unique_members), MEMBERS_PER_FIELD)
        ]

        fields = []

        # First field with summary and leader
        first_chunk = member_chunks[0] if member_chunks else []
        member_text = ", ".join([f"<@{mid}>" for mid in first_chunk])
        if leader_id:
            member_text = f"{leader_mention}, {member_text}" if member_text else leader_mention
        if len(member_chunks) > 1:
            member_text += f" … (+{total_members - len(first_chunk) - (1 if leader_id else 0)} more)"

        summary_value = (
            f"**Role:** {role_mention}\n"
            f"**Members ({total_members}):** {member_text}\n"
            f"**Flag:** `{claimed_flag}`"
        )
        fields.append((f"{status} {faction_name}", summary_value))

        # Optional: Add additional fields for very large member lists
        for idx, chunk in enumerate(member_chunks[1:], start=1):
            chunk_text = ", ".join([f"<@{mid}>" for mid in chunk])
            fields.append((f"{faction_name} (cont. {idx})", chunk_text))

        return fields, discord.Color.green() if role else discord.Color.red()

    @app_commands.command(
        name="list-factions",
        description="List active factions filtered by map."
    )
    @app_commands.choices(map=MAP_CHOICES)
    @app_commands.describe(map="Select a map to list factions from")
    async def list_factions(
        self,
        interaction: discord.Interaction,
        map: app_commands.Choice[str],
    ):
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used inside a server.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            await utils.ensure_connection()
            await ensure_faction_table()
        except Exception as e:
            log.error(f"❌ DB connection failed in {interaction.guild.name}: {e}", exc_info=True)
            return await interaction.followup.send(
                "❌ Failed to connect to the database.", ephemeral=True
            )

        guild = interaction.guild
        guild_id = str(guild.id)
        map_key = map.value.lower()

        try:
            async with utils.safe_acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT faction_name, role_id, leader_id, member_ids, claimed_flag
                    FROM factions
                    WHERE guild_id=$1 AND map=$2
                    ORDER BY faction_name ASC
                    """,
                    guild_id, map_key
                )
        except Exception as e:
            log.error(f"❌ Failed to fetch factions for {guild.name}: {e}", exc_info=True)
            return await interaction.followup.send(
                "❌ Failed to fetch faction list. Please try again later.", ephemeral=True
            )

        if not rows:
            return await interaction.followup.send(
                f"No factions found for {map.value}.", ephemeral=True
            )

        # ---------------- PAGINATION ----------------
        pages = []
        for i in range(0, len(rows), ITEMS_PER_PAGE):
            embed = discord.Embed(
                title=f"🏳️ Active Factions • {map.value}",
                color=discord.Color.blue()
            )
            for row in rows[i:i + ITEMS_PER_PAGE]:
                fields, color = self.make_faction_fields(row, guild)
                for name, value in fields:
                    embed.add_field(name=name, value=value, inline=False)
                embed.color = color  # last faction color
            total_pages = (len(rows) - 1) // ITEMS_PER_PAGE + 1
            embed.set_footer(text=f"Page {len(pages)+1}/{total_pages} • {len(rows)} factions total")
            pages.append(embed)

        # ---------- INTERACTION VIEW FOR NAVIGATION ----------
        class PaginationView(discord.ui.View):
            def __init__(self, pages):
                super().__init__(timeout=120)
                self.pages = pages
                self.current = 0
                self.message = None
                self.update_buttons_state()

            async def update_message(self):
                self.update_buttons_state()
                await self.message.edit(embed=self.pages[self.current], view=self)

            def update_buttons_state(self):
                for child in self.children:
                    if child.label == "⬅️":
                        child.disabled = self.current == 0
                    elif child.label == "➡️":
                        child.disabled = self.current == len(self.pages) - 1

            @discord.ui.button(label="⬅️", style=discord.ButtonStyle.gray)
            async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.current > 0:
                    self.current -= 1
                    await self.update_message()
                await interaction.response.defer()

            @discord.ui.button(label="➡️", style=discord.ButtonStyle.gray)
            async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.current < len(self.pages) - 1:
                    self.current += 1
                    await self.update_message()
                await interaction.response.defer()

        view = PaginationView(pages)
        view.message = await interaction.followup.send(embed=pages[0], ephemeral=True, view=view)
        log.info(f"✅ {interaction.user} listed factions in {guild.name} ({map.value})")


async def setup(bot: commands.Bot):
    await bot.add_cog(FactionList(bot))
