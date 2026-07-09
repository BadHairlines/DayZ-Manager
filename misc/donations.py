import discord
from discord import app_commands
from discord.ext import commands


# ==============================
# THE HIVE DONATION DATA
# ==============================

DONATIONS = {

    "teleporters": {
        "name": "🚀 Teleporters",
        "image": "https://your-image-url.com/teleporter.png",
        "items": [
            {
                "name": "2-Way Teleporter",
                "price": "$18.75 W | $33.75 P",
                "description": "Adds a private two-way teleporter connecting two locations."
            }
        ]
    },


    "bases": {
        "name": "🏠 Base Upgrades",
        "image": "https://your-image-url.com/base.png",
        "items": [

            {
                "name": "🛠 Build Shed",
                "price": "$18.75 W | $33.75 P",
                "description": "Adds a build shed to your faction base."
            },

            {
                "name": "🚪 Bunker Back Door",
                "price": "$22.50 W | $41.25 P",
                "description": "Adds a secondary bunker entrance."
            },

            {
                "name": "📦 Buried Stash",
                "price": "$11.25 W | $18.75 P",
                "description": "Adds a hidden buried stash location."
            },

            {
                "name": "📡 Base Radar (250m)",
                "price": "$12.50 W | $35.00 P",
                "description": "Shows players within 250m of your base. Upgradeable."
            }
        ]
    },


    "vehicles": {
        "name": "🚗 Vehicles",
        "image": "https://your-image-url.com/vehicles.png",
        "items": [

            {
                "name": "Vehicle Spawn",
                "price": "$15 W | $22.50 P",
                "description": "Adds a vehicle spawn point at your base."
            }

        ]
    },


    "faction": {
        "name": "🎖 Faction Extras",
        "image": "https://your-image-url.com/faction.png",
        "items": [

            {
                "name": "Faction Sign",
                "price": "$11.25 W | $18.75 P",
                "description": "Adds a custom faction sign."
            },

            {
                "name": "Campfire Spot",
                "price": "$7.50 W | $15 P",
                "description": "Adds a faction campfire location."
            }

        ]
    },


    "priority": {
        "name": "⚡ Priority Access",
        "image": "https://your-image-url.com/priority.png",
        "items": [

            {
                "name": "Priority Queue Access",
                "price": "$11.25 W | $26.25 P",
                "description": "Skip the queue during peak hours."
            }

        ]
    },


    "addons": {
        "name": "🔧 Server Add-Ons",
        "image": "https://your-image-url.com/addons.png",
        "items": [

            {
                "name": "NPC Spawn",
                "price": "$5",
                "description": "NPC placement until next restart."
            },

            {
                "name": "Loot Spawn",
                "price": "$5",
                "description": "Custom loot spawn up to 10 items."
            },

            {
                "name": "Large Loot Spawn",
                "price": "$2.50",
                "description": "Loot spawn with 10+ items."
            },

            {
                "name": "📢 PA System Spawn",
                "price": "$5",
                "description": "Adds a custom PA System spawn."
            },

            {
                "name": "🔑 Key Spawn",
                "price": "$5",
                "description": "Adds a custom key spawn location."
            },

            {
                "name": "💳 Punch Card Spawn",
                "price": "$5",
                "description": "Adds a military punch card spawn."
            }

        ]
    }
}



# ==============================
# EMBED BUILDERS
# ==============================


def main_embed():

    embed = discord.Embed(
        title="🍯 THE HIVE | Server Donations",
        description=(
            "Support The Hive while unlocking "
            "exclusive server features.\n\n"
            "**W = Wipe**\n"
            "**P = Permanent**\n\n"
            "Select a category below."
        ),
        color=0xF4C430
    )

    return embed



def category_embed(category):

    data = DONATIONS[category]

    embed = discord.Embed(
        title=data["name"],
        color=0xF4C430
    )

    for item in data["items"]:

        embed.add_field(
            name=item["name"],
            value=(
                f"💰 **{item['price']}**\n"
                f"{item['description']}"
            ),
            inline=False
        )


    embed.set_image(url=data["image"])

    return embed



# ==============================
# DROPDOWN
# ==============================


class DonationDropdown(discord.ui.Select):

    def __init__(self):

        options = []

        for key, data in DONATIONS.items():

            options.append(
                discord.SelectOption(
                    label=data["name"],
                    value=key
                )
            )


        super().__init__(
            placeholder="Select a donation category...",
            options=options
        )


    async def callback(self, interaction):

        embed = category_embed(self.values[0])

        await interaction.response.edit_message(
            embed=embed,
            view=DonationView()
        )



# ==============================
# BUTTONS + VIEW
# ==============================


class BackButton(discord.ui.Button):

    def __init__(self):

        super().__init__(
            label="⬅ Back",
            style=discord.ButtonStyle.secondary
        )


    async def callback(self, interaction):

        await interaction.response.edit_message(
            embed=main_embed(),
            view=DonationView()
        )



class DonationView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

        self.add_item(DonationDropdown())
        self.add_item(BackButton())



# ==============================
# COG
# ==============================


class Donations(commands.Cog):

    def __init__(self, bot):

        self.bot = bot



    @app_commands.command(
        name="donations",
        description="View The Hive donation store."
    )
    async def donations(
        self,
        interaction: discord.Interaction
    ):

        await interaction.response.send_message(
            embed=main_embed(),
            view=DonationView()
        )



async def setup(bot):

    await bot.add_cog(Donations(bot))
