import discord
from discord import app_commands
from discord.ext import commands

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

MISC_CHALLENGES = [
    ("Broke", "Have $0 in-game."),
    ("Builder", "Show off your building skills."),
    ("Friendly", "Be friendly to others in-game."),
    ("Hunter", "Capture 5 bears in eggs."),
    ("Asshole", "Tie up & feed a geared player human meat."),
    ("Sellable Hustler", "Sell $25M+ worth of items at once."),
    ("Medic", "Revive/heal 5 different players in one session."),
    ("Ghost", "3 stealth kills without being seen/heard."),
    ("Hoarder", "Fill a tent/container with one weapon type."),
    ("Pyromaniac", "Burn down a base with molotovs or gas grenades."),
    ("Taxi Driver", "Give 5 safe rides to players without killing them."),
    ("Loot Goblin", "Carry $1M+ in loot without dying."),
    ("Rancher", "Tame or trap 10 animals alive."),
    ("Scavenger", "Survive 3 days without a trader."),
    ("Saboteur", "Destroy another player’s vehicle or base."),
    ("Supply Runner", "Deliver supplies to 3 teammates under fire."),
]

ALL_CHALLENGES = COMBAT_CHALLENGES + MARKSMAN_CHALLENGES + KILLSTREAK_CHALLENGES + MISC_CHALLENGES

# ─── DROPDOWNS ───────────────────────────────────────────────────────────────
class ChallengeDropdown(discord.ui.Select):
    def __init__(self, parent_view, category_name, options_list):
        self.parent_view = parent_view
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
        selected_label = self.values[0]
        selected_desc = next((desc for label, desc in ALL_CHALLENGES if label == selected_label), "No description available.")

        # Ping the role if it exists
        role_mention = ""
        if interaction.guild:
            role = discord.utils.get(interaction.guild.roles, name=selected_label)
            if role:
                role_mention = f"{role.mention}\n\n"

        embed = discord.Embed(
            title=f"🏆 {selected_label}",
            description=f"{role_mention}{selected_desc}\n\n**Reward:** $250,000 credits :moneybag: *(proof required)*",
            color=EMBED_COLOR
        )

        await interaction.response.edit_message(embed=embed, view=BackButtonView(self.parent_view))

# ─── VIEWS ───────────────────────────────────────────────────────────────────
class CategoryButton(discord.ui.Button):
    def __init__(self, label, challenges):
        super().__init__(style=discord.ButtonStyle.primary, label=label)
        self.challenges = challenges

    async def callback(self, interaction: discord.Interaction):
        # Small embed for category
        embed = discord.Embed(
            title=f":clipboard: {self.label} Challenges",
            description="Select a challenge from the dropdown below:",
            color=EMBED_COLOR
        )
        view = discord.ui.View()
        view.add_item(ChallengeDropdown(view, self.label, self.challenges))
        view.add_item(BackButton(self.parent_view))  # Add back button to category
        await interaction.response.edit_message(embed=embed, view=view)

class MainMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CategoryButton("Combat", COMBAT_CHALLENGES))
        self.add_item(CategoryButton("Marksman", MARKSMAN_CHALLENGES))
        self.add_item(CategoryButton("Killstreak", KILLSTREAK_CHALLENGES))
        self.add_item(CategoryButton("Misc / Fun", MISC_CHALLENGES))

class BackButton(discord.ui.Button):
    def __init__(self, parent_view):
        super().__init__(style=discord.ButtonStyle.secondary, label="⬅️ Back to Menu")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        main_embed = discord.Embed(
            title=":trophy: THE HIVE — ACCOLADES & CHALLENGES",
            description=(
                "Prove your skill, earn your glory — and claim the rewards you deserve.\n"
                "Each completed challenge earns **$250,000 credits** :moneybag: *(proof required)*"
            ),
            color=EMBED_COLOR
        )
        await interaction.response.edit_message(embed=main_embed, view=self.parent_view)

class BackButtonView(discord.ui.View):
    def __init__(self, parent_view):
        super().__init__(timeout=None)
        self.add_item(BackButton(parent_view))

# ─── COG ─────────────────────────────────────────────────────────────────────
class Challenges(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="challenges", description="View The Hive Challenges")
    async def challenges(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=":trophy: THE HIVE — ACCOLADES & CHALLENGES",
            description=(
                "Select a category below to view challenges.\n"
                "Each completed challenge earns **$250,000 credits** :moneybag: *(proof required)*"
            ),
            color=EMBED_COLOR
        )
        await interaction.response.send_message(embed=embed, view=MainMenuView(), ephemeral=False)

# ─── SETUP ───────────────────────────────────────────────────────────────────
async def setup(bot: commands.Bot):
    await bot.add_cog(Challenges(bot))
