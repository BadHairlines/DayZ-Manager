import discord
from discord import app_commands
from discord.ext import commands

# ─── CONSTANTS ──────────────────────────────────────────────────────────────
EMBED_COLOR = discord.Color.gold()

# ─── CHALLENGE DATA ─────────────────────────────────────────────────────────
COMBAT_CHALLENGES = [
    ("Pistolier", "Kill an enemy with a spawn pistol."),
    ("Brutalized", "Kill with a weapon buttstock."),
    ("Haymaker", "Kill with your fists."),
    ("No Scope", "Sniper kill with no optic."),
    ("Assassin", "5 sword kills."),
    ("Bullseye", "Kill someone climbing a ladder."),
    ("Sleight of Hand", "Run out of ammo and finish with a pistol."),
    ("Danger Close", "Kill 4 enemies with one explosive."),
    ("Roadkill", "Run over and kill an enemy."),
    ("Medal of Honor", "Jump on a live grenade to save a teammate."),
    ("Executioner", "Finish an unconscious enemy."),
    ("One Tap Wonder", "One headshot kill from full health."),
    ("Reaper", "10 kills in one life.")
]

MARKSMAN_CHALLENGES = [
    ("Sharpshooter", "Kill over 500m."),
    ("Marksmen", "Kill over 800m."),
    ("Elite Marksmen", "Kill over 900m."),
    ("Headshot", "Get 50 headshots."),
    ("Decapitated", "Get 100 headshots."),
    ("Eagle Eye", "Moving target kill at 700m+."),
    ("Wind Whisperer", "Snipe through wind or fog."),
    ("Unstoppable", "2.30+ KD with 100 kills.")
]

KILLSTREAK_CHALLENGES = [
    ("25 Kill Streak", "Achieve a 25 kill streak."),
    ("50 Kill Streak", "Achieve a 50 kill streak."),
    ("100 Kill Streak", "Achieve a 100 kill streak."),
    ("Kill Streak Master", "50+ streak."),
    ("Shock and Awe", "1,000 total kills."),
    ("Last Stand", "Get up and kill who downed you."),
    ("Hostile", "Get 200 kills."),
    ("Hive Dominator", "Hold top kill leaderboard for a week."),
    ("Master of Challenges", "Complete all challenges.")
]

# ─── DROPDOWN CLASSES ────────────────────────────────────────────────────────
class ChallengeDropdown(discord.ui.Select):
    def __init__(self, category_name, options_list):
        select_options = [
            discord.SelectOption(label=name, description=desc[:100] if desc else None)
            for name, desc in options_list
        ]
        super().__init__(
            placeholder=f"Select a {category_name} Challenge",
            min_values=1,
            max_values=1,
            options=select_options
        )

    async def callback(self, interaction: discord.Interaction):
        # Show full challenge info ephemeral
        selected_label = self.values[0]
        selected_desc = next(
            (desc for label, desc in COMBAT_CHALLENGES + MARKSMAN_CHALLENGES + KILLSTREAK_CHALLENGES
             if label == selected_label),
            "No description available."
        )
        embed = discord.Embed(
            title=f"🏆 {selected_label}",
            description=selected_desc + "\n\n**Reward:** $250,000 credits :moneybag: *(proof required)*",
            color=EMBED_COLOR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ChallengeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ChallengeDropdown("Combat", COMBAT_CHALLENGES))
        self.add_item(ChallengeDropdown("Marksman", MARKSMAN_CHALLENGES))
        self.add_item(ChallengeDropdown("Killstreak", KILLSTREAK_CHALLENGES))

# ─── COG ─────────────────────────────────────────────────────────────────────
class Challenges(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="challenges", description="View The Hive Challenges")
    async def challenges(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=":trophy: THE HIVE — ACCOLADES & CHALLENGES",
            description=(
                "Prove your skill, earn your glory — and claim the rewards you deserve.\n"
                "Each completed challenge earns **$250,000 credits** :moneybag: *(proof required)*"
            ),
            color=EMBED_COLOR
        )
        embed.add_field(name=":crossed_swords: Combat Challenges", value="\u200b", inline=False)
        embed.add_field(name=":dart: Marksman Challenges", value="\u200b", inline=False)
        embed.add_field(name=":fire: Killstreak Challenges", value="\u200b", inline=False)

        await interaction.response.send_message(embed=embed, view=ChallengeView(), ephemeral=False)

# ─── SETUP ───────────────────────────────────────────────────────────────────
async def setup(bot: commands.Bot):
    await bot.add_cog(Challenges(bot))
