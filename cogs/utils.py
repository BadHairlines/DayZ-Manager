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
    "livonia": {
        "name": "Livonia",
        "image": "https://i.postimg.cc/QN9vfr9m/Livonia.jpg"
    },
    "chernarus": {
        "name": "Chernarus",
        "image": "https://i.postimg.cc/3RWzMsLK/Chernarus.jpg"
    },
    "sakhal": {
        "name": "Sakhal",
        "image": "https://i.postimg.cc/HkBSpS8j/Sakhal.png"
    },
}

# Custom emoji placeholders (replace values with actual emoji IDs if you have them)
CUSTOM_EMOJIS = {
    flag: f":{flag}:" for flag in FLAGS
}


def load_data():
    """Safely load server data from JSON file."""
    global server_vars
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                content = f.read().strip()
                server_vars = json.loads(content) if content else {}
            print("✅ Loaded server data successfully.")
        except (json.JSONDecodeError, FileNotFoundError):
            print("⚠️ Corrupted or missing JSON, resetting data.")
            server_vars = {}
    else:
        server_vars = {}


async def save_data():
    """Save server data to JSON file."""
    async with data_lock:
        with open(DATA_FILE, "w") as f:
            json.dump(server_vars, f, indent=4)
