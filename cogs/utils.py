import os
import json
from asyncio import Lock

DATA_FILE = "server_vars.json"
data_lock = Lock()
server_vars = {}

FLAGS = [
    "Altis", "APA", "BabyDeer", "Bear", "Bohemia", "BrainZ", "Cannibals", "CDF",
    "CHEL", "Chedaki", "Chernarus", "CMC", "Crook", "DayZ", "HunterZ", "NAPA",
    "Livonia", "LivoniaArmy", "LivoniaPolice", "NSahrani", "Pirates", "Rex",
    "Refuge", "Rooster", "RSTA", "Snake", "SSahrani", "TEC", "UEC", "Wolf",
    "Zagorky", "Zenit"
]

MAP_DATA = {
    "livonia": {"name": "Livonia", "image": "https://i.postimg.cc/QN9vfr9m/Livonia.jpg"},
    "chernarus": {"name": "Chernarus", "image": "https://i.postimg.cc/3RWzMsLK/Chernarus.jpg"},
    "sakhal": {"name": "Sakhal", "image": "https://i.postimg.cc/HkBSpS8j/Sakhal.png"},
}

CUSTOM_EMOJIS = {
    "Altis": "<:Altis:1234567890>",
    "APA": "<:APA:1234567890>",
    "BabyDeer": "<:BabyDeer:1234567890>",
    # Add all emojis here
}

def load_data():
    global server_vars
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            server_vars = json.load(f)
    else:
        server_vars = {}

async def save_data():
    from asyncio import Lock
    async with data_lock:
        with open(DATA_FILE, "w") as f:
            json.dump(server_vars, f, indent=4)
