import discord
from discord import app_commands
from discord.ext import commands

EMBED_COLOR = discord.Color.gold()

# ─── CHALLENGE DATA ───────────────────────────────────────────────────────────
COMBAT_CHALLENGES = [
    ("Pistolier", "Kill an enemy with a spawn pistol.", 50000),
    ("Brutalized", "Kill with a weapon buttstock.", 75000),
    ("Haymaker", "Kill with your fists.", 60000),
    ("No Scope", "Sniper kill with no optic.", 100000),
    ("Assassin", "5 sword kills.", 120000),
    ("Bullseye", "Kill someone climbing a ladder.", 90000),
    ("Sleight of Hand", "Run out of ammo and finish with a pistol.", 110000),
    ("Danger Close", "Kill 4 enemies with one explosive.", 150000),
    ("Roadkill", "Run over and kill an enemy.", 80000),
    ("Medal of Honor", "Jump on a live grenade to save a teammate.", 200000),
    ("Executioner", "Finish an unconscious enemy.", 130000),
    ("One Tap Wonder", "One headshot kill from full health.", 125000),
    ("Reaper", "10 kills in one life.", 180000)
]

MARKSMAN_CHALLENGES = [
    ("Sharpshooter", "Kill over 500m.", 75000),
    ("Marksmen", "Kill over 800m.", 100000),
    ("Elite Marksmen", "Kill over 900m.", 125000),
    ("Headshot", "Get 50 headshots.", 150000),
    ("Decapitated", "Get 100 headshots.", 200000),
    ("Eagle Eye", "Moving target kill at 700m+.", 175000),
    ("Wind Whisperer", "Snipe through wind or fog.", 200000),
    ("Unstoppable", "2.30+ KD with 100 kills.", 250000)
]

KILLSTREAK_CHALLENGES = [
    ("25 Kill Streak", "Achieve a 25 kill streak.", 100000),
    ("50 Kill Streak", "Achieve a 50 kill streak.", 150000),
    ("100 Kill Streak", "Achieve a 100 kill streak.", 250000),
    ("Kill Streak Master", "50+ streak.", 175000),
    ("Shock and Awe", "1,000 total kills.", 300000),
    ("Last Stand", "Get up and kill who downed you.", 120000),
    ("Hostile", "Get 200 kills.", 225000),
    ("Hive Dominator", "Hold top kill leaderboard for a week.", 400000),
    ("Master of Challenges", "Complete all challenges.", 500000)
]

MISC_CHALLENGES = [
    ("Broke", "Have $0 in-game.", 20000),
    ("Builder", "Show off your building skills.", 50000),
    ("Friendly", "Be friendly to others in-game.", 40000),
    ("Hunter", "Capture 5 bears in eggs.", 60000),
    ("Asshole", "Tie up & feed a geared player human meat.", 100000),
    ("Sellable Hustler", "Sell $25M+ worth of items at once.", 200000),
    ("Medic", "Revive/heal 5 different players in one session.", 75000),
    ("Ghost", "3 stealth kills without being seen/heard.", 90000),
    ("Hoarder", "Fill a tent/container with one weapon type.", 80000),
    ("Pyromaniac", "Hit a base with a gas strike.", 150000),
    ("Taxi Driver", "Give 5 safe rides to randoms without killing them.", 40000),
    ("Loot Goblin", "Carry $1M+ in loot without dying.", 100000),
    ("Rancher", "Trap 10 animals alive.", 85000),
    ("Scavenger", "Survive 10 days without dying.", 90000),
    ("Saboteur", "Destroy another player’s vehicle or base.", 120000),
    ("Supply Runner", "Deliver supplies to 3 teammates under fire.", 75000)
]

ALL_CHALLENGES = COMBAT_CHALLENGES + MARKSMAN_CHALLENGES + KILLSTREAK_CHALLENGES + MISC_CHALLENGES

# ─── BUTTONS ─────────────────────────────────────────────────────────────────
class BackToCategoryButton(discord.ui.Button):
    def __init__(self, category_name, challenges_list):
        super().__init__(style=discord.ButtonStyle.primary, label="Back to Category")
        self.category_name = category_name
        self.challenges_list = challenges_list

    async def callback(self, interaction: discord.Interaction):
        view = discord.ui.View()
        view.add_item(ChallengeDropdown(self.category_name, self.challenges_list))
        embed = discord.Embed(
            title=f":clipboard: {self.category_name} Challenges",
            description="Select a challenge from the dropdown below:",
            color=EMBED_COLOR
        )
        await interaction.response.edit_message(embed=embed, view=view)

class ChallengeDropdown(discord.ui.Select):
    def __init__(self, category_name, challenges_list):
        options = [
            discord.SelectOption(label=name, description=f"{desc[:80]} | Reward: ${reward:,}")
            for name, desc, reward in challenges_list
        ]
        super().__init__(placeholder=f"Select a {category_name} Challenge", min_values=1, max_values=1, options=options)
        self.category_name = category_name
        self.challenges_list = challenges_list

    async def callback(self, interaction: discord.Interaction):
        selected_name = self.values[0]
        selected = next((n, d, r) for n, d, r in ALL_CHALLENGES if n == selected_name)
        name, desc, reward = selected

        role_mention = ""
        if interaction.guild:
            role = discord.utils.get(interaction.guild.roles, name=name)
            if role:
                role_mention = f"{role.mention}\n\n"

        embed = discord.Embed(
            title=f"🏆 {name}",
            description=f"{role_mention}{desc}\n\n**Reward:** ${reward:,} credits :moneybag: *(proof required)*",
            color=EMBED_COLOR
        )

        view = discord.ui.View()
        view.add_item(BackToCategoryButton(self.category_name, self.challenges_list))
        await interaction.response.edit_message(embed=embed, view=view)

class CategoryButton(discord.ui.Button):
    def __init__(self, label, emoji, challenges):
        super().__init__(style=discord.ButtonStyle.primary, label=label, emoji=emoji)
        self.challenges = challenges

    async def callback(self, interaction: discord.Interaction):
        view = discord.ui.View()
        view.add_item(ChallengeDropdown(self.label, self.challenges))

        embed = discord.Embed(
            title=f":clipboard: {self.label} Challenges",
            description="Select a challenge from the dropdown below:",
            color=EMBED_COLOR
        )

        # Anyone can use the buttons
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )

class MainMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CategoryButton("Combat", "⚔️", COMBAT_CHALLENGES))
        self.add_item(CategoryButton("Marksman", "🎯", MARKSMAN_CHALLENGES))
        self.add_item(CategoryButton("Killstreak", "💥", KILLSTREAK_CHALLENGES))
        self.add_item(CategoryButton("Misc / Fun", "🎲", MISC_CHALLENGES))

# ─── COG ─────────────────────────────────────────────────────────────────────
class Challenges(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.challenge_message = None
        self.channel = None

    @app_commands.command(name="challenges", description="Create or show the Challenges menu")
    async def challenges(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        # --- Admin-only check ---
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "Only server admins can use this command.", ephemeral=True
            )
            return

        # Find or create #challenges channel
        if not self.channel:
            self.channel = discord.utils.get(guild.text_channels, name="🏆┃challenges")
        if not self.channel:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(send_messages=False)
            }
            self.channel = await guild.create_text_channel(
                "challenges", overwrites=overwrites, reason="Created Challenges channel"
            )

        # Check if main menu message already exists
        if not self.challenge_message:
            existing = [m async for m in self.channel.history(limit=50) if m.author == self.bot.user]
            for m in existing:
                try:
                    await m.fetch()
                    self.challenge_message = m
                    break
                except discord.NotFound:
                    continue

            if not self.challenge_message:
                embed = discord.Embed(
                    title=":trophy: THE HIVE — ACCOLADES & CHALLENGES",
                    description=(
                        "Select a category below to view challenges.\n"
                        "Each completed challenge earns its respective reward :moneybag: *(proof required)*"
                    ),
                    color=EMBED_COLOR
                )
                rules_text = (
                    "1️⃣ Must have kill-feed or recorded proof.\n"
                    "2️⃣ If no kill-feed, submit video proof in a ticket.\n"
                    "3️⃣ Exploiting or cheating = all accolades removed + permanent ban.\n"
                    "4️⃣ To redeem, open a support ticket and include your proof/video."
                )
                embed.add_field(name=":triangular_flag_on_post: Rules & Redemption", value=rules_text, inline=False)

                self.challenge_message = await self.channel.send(embed=embed, view=MainMenuView())
                await self.challenge_message.pin()

        await interaction.response.send_message(
            f"The challenges menu is ready in {self.channel.mention}.", ephemeral=True
        )

# ─── SETUP ───────────────────────────────────────────────────────────────────
async def setup(bot: commands.Bot):
    await bot.add_cog(Challenges(bot))
