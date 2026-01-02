import discord
from discord.ext import commands
from discord import app_commands

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

class ChallengeDropdown(discord.ui.Select):
    def __init__(self, category_name, options_list):
        # Convert your challenge list to discord.SelectOption
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
        await interaction.response.send_message(
            f"You selected **{self.values[0]}**!", ephemeral=True
        )

class ChallengeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        # Combat Challenges
        combat = [
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
        self.add_item(ChallengeDropdown("Combat", combat))

        # Marksman Challenges
        marksman = [
            ("Sharpshooter", "Kill over 500m."),
            ("Marksmen", "Kill over 800m."),
            ("Elite Marksmen", "Kill over 900m."),
            ("Headshot", "Get 50 headshots."),
            ("Decapitated", "Get 100 headshots."),
            ("Eagle Eye", "Moving target kill at 700m+."),
            ("Wind Whisperer", "Snipe through wind or fog."),
            ("Unstoppable", "2.30+ KD with 100 kills.")
        ]
        self.add_item(ChallengeDropdown("Marksman", marksman))

        # Killstreak Challenges
        killstreak = [
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
        self.add_item(ChallengeDropdown("Killstreak", killstreak))


@bot.tree.command(name="challenges", description="View The Hive Challenges")
async def challenges(interaction: discord.Interaction):
    embed = discord.Embed(
        title=":trophy: THE HIVE — ACCOLADES & CHALLENGES",
        description=(
            "Prove your skill, earn your glory — and claim the rewards you deserve.\n"
            "Each completed challenge earns **$250,000 credits** :moneybag: *(proof required)*"
        ),
        color=discord.Color.gold()
    )
    embed.add_field(name=":crossed_swords: Combat Challenges", value="\u200b", inline=False)
    embed.add_field(name=":dart: Marksman Challenges", value="\u200b", inline=False)
    embed.add_field(name=":fire: Killstreak Challenges", value="\u200b", inline=False)

    await interaction.response.send_message(embed=embed, view=ChallengeView(), ephemeral=False)

bot.run("YOUR_BOT_TOKEN")
