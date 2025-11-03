import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import json
import os
from datetime import datetime


PROGRESS_FILE = "dm_progress.json"


class DMRole(commands.Cog):
    """Safely DM every user in a selected role (supports 1000+ users with resume support)."""

    def __init__(self, bot):
        self.bot = bot

    def save_progress(self, guild_id, role_id, sent_ids):
        """Save DM progress to file so it can resume later."""
        data = {}
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, "r") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = {}

        data[f"{guild_id}_{role_id}"] = sent_ids
        with open(PROGRESS_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def load_progress(self, guild_id, role_id):
        """Load existing progress if available."""
        if not os.path.exists(PROGRESS_FILE):
            return set()
        try:
            with open(PROGRESS_FILE, "r") as f:
                data = json.load(f)
            return set(data.get(f"{guild_id}_{role_id}", []))
        except Exception:
            return set()

    @app_commands.command(
        name="dm-role",
        description="Safely DM all members in a role (resumable + rate-limited)."
    )
    @app_commands.describe(
        role="Which role to DM",
        message="The message to send (plain text, links included)"
    )
    async def dm_role(self, interaction: discord.Interaction, role: discord.Role, message: str):
        await interaction.response.defer(thinking=True, ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("🚫 Admins only.", ephemeral=True)

        members = [m for m in role.members if not m.bot]
        total = len(members)

        if total == 0:
            return await interaction.followup.send("⚠️ No human members found in that role.", ephemeral=True)

        # Load previous progress
        sent_ids = self.load_progress(interaction.guild.id, role.id)
        remaining = [m for m in members if str(m.id) not in sent_ids]

        await interaction.followup.send(
            f"📬 Starting DM batch for **{role.name}** ({len(remaining)} users left out of {total}).",
            ephemeral=True
        )

        success, failed = 0, 0

        for i, member in enumerate(remaining, start=1):
            try:
                await member.send(message)
                success += 1
                sent_ids.add(str(member.id))
                # Save progress every 10 users
                if i % 10 == 0:
                    self.save_progress(interaction.guild.id, role.id, list(sent_ids))

            except discord.Forbidden:
                failed += 1
            except Exception as e:
                failed += 1
                print(f"⚠️ DM failed for {member}: {e}")

            if i % 10 == 0:
                await interaction.edit_original_response(
                    content=f"📨 Sent `{success}` / `{total}` messages so far... (failed: {failed})"
                )

            # Rate-limit friendly delay
            await asyncio.sleep(1.5)

        # Final save + cleanup
        self.save_progress(interaction.guild.id, role.id, list(sent_ids))

        complete_msg = (
            f"✅ Finished DM batch for **{role.name}**\n"
            f"📤 Sent: {success}\n"
            f"⚠️ Failed: {failed}\n"
            f"🕒 Completed at <t:{int(datetime.utcnow().timestamp())}:f>"
        )
        await interaction.edit_original_response(content=complete_msg)


async def setup(bot: commands.Bot):
    await bot.add_cog(DMRole(bot))
