from __future__ import annotations

import html
import io
import json
import logging
import os
import re
import secrets
import time
import zipfile
from urllib.parse import quote, urlencode

import aiohttp

from aiohttp import web
import discord
from discord.ext import commands

from cogs import utils
from misc.teleporter import ALLOWED_GUILD_IDS

log = logging.getLogger("dayz-manager")


# =========================================================
# DISCORD OAUTH / PRIVATE WEB SESSIONS
# =========================================================

DISCORD_API = "https://discord.com/api/v10"
DISCORD_OAUTH_AUTHORIZE = "https://discord.com/oauth2/authorize"
DISCORD_OAUTH_TOKEN = f"{DISCORD_API}/oauth2/token"
ADMINISTRATOR_PERMISSION = 1 << 3
SESSION_COOKIE = "dzm_session"
STATE_COOKIE = "dzm_oauth_state"
SESSION_TTL = 8 * 60 * 60
STATE_TTL = 10 * 60

# Server-side sessions: browsers only receive random opaque IDs.
WEB_SESSIONS: dict[str, dict] = {}
OAUTH_STATES: dict[str, float] = {}

FLAG_IMAGES: dict[str, str] = {
    "APA": "https://i.postimg.cc/HW60bB1p/APA.png",
    "Altis": "https://i.postimg.cc/KjfMfcHq/Altis.png",
    "BabyDeer": "https://i.postimg.cc/Hk5QG3GC/BabyDeer.png",
    "Bear": "https://i.postimg.cc/qBxy4Qvs/Bear.png",
    "Bohemia": "https://i.postimg.cc/R0Bwvf9J/Bohemia.png",
    "BrainZ": "https://i.postimg.cc/X7NFJFrT/BrainZ.png",
    "Cannibals": "https://i.postimg.cc/MGmVHTKP/Cannibals.png",
    "CHEL": "https://i.postimg.cc/QCMj1XGJ/CHEL.png",
    "Chedaki": "https://i.postimg.cc/PxytCCcq/Chedaki.png",
    "CMC": "https://i.postimg.cc/3rL87DmS/CMC.png",
    "Crook": "https://i.postimg.cc/cLrn7SMh/Crook.png",
    "HunterZ": "https://i.postimg.cc/zXVJfXkJ/HunterZ.png",
    "NAPA": "https://i.postimg.cc/152yVhWD/NAPA.png",
    "NSahrani": "https://i.postimg.cc/0QqKqJgX/NSahrani.png",
    "Pirates": "https://i.postimg.cc/gJMhyTh3/Pirates.png",
    "Rex": "https://i.postimg.cc/ydXg6Ys1/Rex.png",
    "Refuge": "https://i.postimg.cc/NF5Hdk8S/Refuge.png",
    "Rooster": "https://i.postimg.cc/9Q9CG8SK/Rooster.png",
    "RSTA": "https://i.postimg.cc/pr4n45qT/RSTA.png",
    "Snake": "https://i.postimg.cc/66mRyFtX/Snake.png",
    "TEC": "https://i.postimg.cc/R0z9G1xF/TEC.png",
    "UEC": "https://i.postimg.cc/hjDnRSjR/UEC.png",
    "Wolf": "https://i.postimg.cc/vB0sQpgg/Wolf.png",
    "Zagorky": "https://i.postimg.cc/7P9Gp6KX/Zagorky.png",
    "Zenit": "https://i.postimg.cc/rszLzQxh/Zenit.png",
}


def _prune_web_auth() -> None:
    now = time.time()
    for key, session in list(WEB_SESSIONS.items()):
        if float(session.get("expires_at", 0)) <= now:
            WEB_SESSIONS.pop(key, None)
    for key, expires_at in list(OAUTH_STATES.items()):
        if expires_at <= now:
            OAUTH_STATES.pop(key, None)


def _oauth_client_id(bot: commands.Bot) -> str | None:
    value = os.getenv("DISCORD_CLIENT_ID", "").strip()
    if value:
        return value
    return str(bot.user.id) if bot.user else None


def _oauth_client_secret() -> str | None:
    return os.getenv("DISCORD_CLIENT_SECRET", "").strip() or None


def _oauth_redirect_uri() -> str | None:
    explicit = os.getenv("DISCORD_OAUTH_REDIRECT_URI", "").strip()
    if explicit:
        return explicit
    base = public_base_url()
    return f"{base}/auth/discord/callback" if base else None


def _current_session(request: web.Request) -> dict | None:
    _prune_web_auth()
    session_id = request.cookies.get(SESSION_COOKIE, "")
    session = WEB_SESSIONS.get(session_id)
    if not session:
        return None
    if float(session.get("expires_at", 0)) <= time.time():
        WEB_SESSIONS.pop(session_id, None)
        return None
    return session


def _discord_avatar_url(user: dict) -> str | None:
    user_id = str(user.get("id") or "")
    avatar = user.get("avatar")
    if user_id and avatar:
        ext = "gif" if str(avatar).startswith("a_") else "png"
        return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}.{ext}?size=128"
    return None


def _can_admin_oauth_guild(guild: dict) -> bool:
    if bool(guild.get("owner")):
        return True
    try:
        return bool(int(guild.get("permissions", "0")) & ADMINISTRATOR_PERMISSION)
    except (TypeError, ValueError):
        return False


def _authorized_web_guild(request: web.Request, guild_id: str) -> tuple[dict | None, discord.Guild | None]:
    """Return the authenticated session + live guild only when this user may administer it."""
    session = _current_session(request)
    if not session or str(guild_id) not in set(session.get("guild_ids", [])):
        return None, None
    bot: commands.Bot = request.app["bot"]
    try:
        guild = bot.get_guild(int(guild_id))
    except (TypeError, ValueError):
        guild = None
    if guild is None:
        return None, None
    return session, guild


def _require_csrf(request: web.Request, session: dict) -> bool:
    supplied = request.headers.get("X-CSRF-Token", "")
    expected = str(session.get("csrf_token") or "")
    return bool(supplied and expected and secrets.compare_digest(supplied, expected))


async def _request_json(request: web.Request) -> dict:
    try:
        data = await request.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _setup_key(map_key: str, server: str) -> str:
    return f"{utils.normalize_map(map_key)}::{utils.normalize_server(server)}"


async def _refresh_flag_dashboard(bot: commands.Bot, guild: discord.Guild, map_key: str, server: str) -> tuple[bool, str]:
    from cogs.ui.flag_views import FlagManageView
    stored = await utils.get_flag_message(str(guild.id), map_key, server)
    if not stored:
        return False, "No stored public flag message was found for that setup."
    channel = guild.get_channel(int(stored["channel_id"]))
    if not isinstance(channel, discord.TextChannel):
        return False, "The stored flag channel no longer exists."
    try:
        message = await channel.fetch_message(int(stored["message_id"]))
    except discord.NotFound:
        return False, "The stored dashboard message no longer exists. Use Setup to recreate it."
    except discord.Forbidden:
        return False, "DayZ Manager cannot access the stored dashboard message."
    except discord.HTTPException:
        return False, "Discord returned an error while reading the stored dashboard."

    view = await FlagManageView.create(guild, map_key, server, bot)
    try:
        bot.add_view(view, message_id=message.id)
    except ValueError:
        pass

    if getattr(message.flags, "components_v2", False):
        await message.edit(view=view)
    else:
        try:
            await message.delete()
        except discord.HTTPException:
            pass
        message = await channel.send(view=view)
        await utils.save_flag_message(
            str(guild.id), map_key, server, str(channel.id), str(message.id)
        )
    return True, f"Dashboard refreshed in #{channel.name}."


def _normalize_position(position: str) -> list[int | float]:
    position = str(position or "").strip().replace(" ", "")
    if not position.startswith("["):
        position = f"[{position}]"
    data = json.loads(position)
    if not isinstance(data, list) or len(data) != 3:
        raise ValueError("Position must contain exactly 3 coordinates.")
    if any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in data):
        raise ValueError("Coordinates must be numbers.")
    return data


def _clean_file_name(value: str) -> str:
    value = str(value or "").strip().replace(" ", "_")
    value = "".join(ch for ch in value if ch.isalnum() or ch in "_-")
    return value or "Unknown"


# =========================================================
# URL HELPERS
# =========================================================

def public_base_url() -> str | None:
    """Public website base used by Discord dashboard link buttons."""
    explicit = (
        os.getenv("DAYZ_MANAGER_BASE_URL", "").strip().rstrip("/")
        or os.getenv("FLAG_WEB_BASE_URL", "").strip().rstrip("/")
    )
    if explicit:
        if not explicit.startswith(("http://", "https://")):
            explicit = f"https://{explicit}"
        return explicit

    railway = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip().rstrip("/")
    if railway:
        return f"https://{railway}"

    return None


def _slug(value: str) -> str:
    value = str(value or "").strip().casefold()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "server"


def flag_page_url(guild_id: int | str, map_key: str, server: str) -> str | None:
    base = public_base_url()
    if not base:
        return None
    map_part = quote(utils.normalize_map(map_key), safe="")
    server_part = quote(_slug(utils.normalize_server(server)), safe="")
    return f"{base}/flags/{guild_id}/{map_part}/{server_part}"


# =========================================================
# DATA HELPERS
# =========================================================

async def _get_payload(bot: commands.Bot, guild_id: str, map_key: str, server: str) -> dict | None:
    map_key = utils.normalize_map(map_key)
    server = utils.normalize_server(server)
    rows = await utils.get_all_flags(guild_id, map_key, server)
    if not rows:
        return None

    guild = None
    try:
        guild = bot.get_guild(int(guild_id))
    except (TypeError, ValueError):
        pass

    available: list[dict] = []
    claimed: list[dict] = []
    for row in sorted(rows, key=lambda r: str(r["flag"]).casefold()):
        flag_name = str(row["flag"])
        item = {"flag": flag_name, "image": FLAG_IMAGES.get(flag_name)}
        is_claimed = bool(row["role_id"] or row["status"] == "❌")
        if is_claimed:
            role_id = str(row["role_id"]) if row["role_id"] else None
            role_name = "Assigned"
            if guild and role_id:
                try:
                    role = guild.get_role(int(role_id))
                    if role:
                        role_name = role.name
                except (TypeError, ValueError):
                    pass
            item.update({"role_id": role_id, "role_name": role_name})
            claimed.append(item)
        else:
            available.append(item)

    map_info = utils.MAP_DATA.get(map_key, {"name": map_key.title(), "image": None})
    total = len(rows)
    claimed_pct = round((len(claimed) / total) * 100) if total else 0

    return {
        "guild_id": str(guild_id),
        "guild_name": guild.name if guild else "DayZ Server",
        "guild_icon": str(guild.icon.url) if guild and guild.icon else None,
        "map": map_key,
        "map_name": map_info.get("name", map_key.title()),
        "map_image": map_info.get("image"),
        "server": server,
        "server_slug": _slug(server),
        "total": total,
        "available_count": len(available),
        "claimed_count": len(claimed),
        "claimed_pct": claimed_pct,
        "available": available,
        "claimed": claimed,
        "url": flag_page_url(guild_id, map_key, server),
    }


async def _public_setups(bot: commands.Bot) -> list[dict]:
    rows = await utils.get_public_flag_sessions()
    result: list[dict] = []
    for row in rows:
        guild_id = str(row["guild_id"])
        guild = None
        try:
            guild = bot.get_guild(int(guild_id))
        except (TypeError, ValueError):
            pass
        # Do not publish stale setups from Discord servers the bot is no longer in.
        if guild is None:
            continue

        map_key = utils.normalize_map(row["map"])
        server = utils.normalize_server(row["server"])
        map_info = utils.MAP_DATA.get(map_key, {"name": map_key.title(), "image": None})
        total = int(row["total"] or 0)
        available_count = int(row["available_count"] or 0)
        claimed_count = int(row["claimed_count"] or 0)
        result.append({
            "guild_id": guild_id,
            "guild_name": guild.name,
            "guild_icon": str(guild.icon.url) if guild.icon else None,
            "map": map_key,
            "map_name": map_info.get("name", map_key.title()),
            "map_image": map_info.get("image"),
            "server": server,
            "server_slug": _slug(server),
            "total": total,
            "available_count": available_count,
            "claimed_count": claimed_count,
            "claimed_pct": round((claimed_count / total) * 100) if total else 0,
            "url": flag_page_url(guild_id, map_key, server),
        })
    return result


async def _resolve_server_slug(guild_id: str, map_key: str, server_slug: str) -> str | None:
    sessions = await utils.get_guild_flag_setups(guild_id)
    map_key = utils.normalize_map(map_key)
    wanted = _slug(server_slug)
    for row in sessions:
        if utils.normalize_map(row["map"]) != map_key:
            continue
        server = utils.normalize_server(row["server"])
        if _slug(server) == wanted:
            return server
    return None


# =========================================================
# SHARED SITE CHROME
# =========================================================

SITE_CSS = r"""
:root{--bg:#090d12;--panel:#111821;--panel2:#0d141c;--line:#283545;--text:#f5f7fb;--muted:#92a5bb;--blue:#57a8ff;--green:#43e99c;--red:#ff5775;--gold:#f2d85e;--shadow:0 22px 70px #0008}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:radial-gradient(circle at 20% -10%,#1a2839 0,transparent 38%),radial-gradient(circle at 90% 10%,#171f2b 0,transparent 30%),var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;min-height:100vh}a{color:inherit;text-decoration:none}.wrap{width:min(1180px,calc(100% - 34px));margin:auto}.nav{height:78px;display:flex;align-items:center;justify-content:space-between;gap:20px}.brand{display:flex;align-items:center;gap:12px;font-weight:900;font-size:20px}.brandmark{width:39px;height:39px;border:1px solid var(--line);background:linear-gradient(145deg,#1e2a39,#111821);border-radius:12px;display:grid;place-items:center;box-shadow:0 10px 30px #0005}.navlinks{display:flex;gap:7px;align-items:center;flex-wrap:wrap}.navlinks a{padding:9px 12px;border-radius:10px;color:#b9c7d6;font-size:14px}.navlinks a:hover{background:#16202b;color:#fff}.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:12px 16px;border-radius:12px;border:1px solid var(--line);background:#151f2a;font-weight:750;transition:.18s transform,.18s border-color,.18s background}.btn:hover{transform:translateY(-1px);border-color:#49617b;background:#1a2735}.btn.primary{background:linear-gradient(135deg,#4b9cff,#7667ff);border-color:transparent;color:#fff;box-shadow:0 12px 35px #4d75ff33}.hero-home{padding:72px 0 55px;display:grid;grid-template-columns:1.15fr .85fr;gap:45px;align-items:center}.eyebrow{display:inline-flex;gap:9px;align-items:center;color:#afc3d8;border:1px solid var(--line);border-radius:999px;padding:7px 11px;background:#111923aa;font-size:12px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.dot{width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 14px var(--green)}h1{font-size:clamp(42px,7vw,78px);line-height:.98;letter-spacing:-3px;margin:18px 0 20px}.gradient{background:linear-gradient(100deg,#fff 5%,#82bfff 48%,#9d8cff 88%);-webkit-background-clip:text;background-clip:text;color:transparent}.lead{font-size:18px;line-height:1.7;color:#a7b7c9;max-width:720px}.hero-actions{display:flex;gap:11px;flex-wrap:wrap;margin-top:28px}.mock{background:linear-gradient(145deg,#121b25,#0c1118);border:1px solid var(--line);border-radius:25px;padding:19px;box-shadow:var(--shadow);transform:rotate(1.1deg)}.mock-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}.mini-stat-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.mini-stat{background:#0b1118;border:1px solid #233041;border-radius:14px;padding:13px}.mini-stat strong{display:block;font-size:22px}.mini-list{margin-top:10px;border:1px solid #243141;border-radius:14px;overflow:hidden}.mini-row{padding:11px 13px;border-bottom:1px solid #1f2b39;display:flex;justify-content:space-between;font-size:13px}.mini-row:last-child{border:0}.section{padding:58px 0}.section-title{font-size:clamp(29px,4vw,42px);letter-spacing:-1.5px;margin:0 0 10px}.section-sub{color:var(--muted);max-width:740px;line-height:1.6}.feature-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:28px}.feature{background:linear-gradient(180deg,#111923,#0d131a);border:1px solid var(--line);border-radius:18px;padding:22px}.feature .icon{font-size:26px}.feature h3{margin:14px 0 7px}.feature p{color:var(--muted);line-height:1.55;font-size:14px;margin:0}.stat-band{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:25px}.big-stat{border:1px solid var(--line);background:#101720;border-radius:17px;padding:20px}.big-stat strong{font-size:30px;display:block}.big-stat span{color:var(--muted);font-size:13px}.card{background:linear-gradient(180deg,#111821,#0d131a);border:1px solid var(--line);border-radius:20px;box-shadow:0 15px 40px #0004}.directory-tools{display:flex;gap:10px;margin:22px 0}.search{width:100%;padding:14px 16px;border-radius:13px;border:1px solid var(--line);background:#0c1219;color:#fff;outline:none;font-size:15px}.search:focus{border-color:#567596}.server-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.server-card{padding:19px;display:flex;gap:15px;align-items:flex-start}.server-icon{width:48px;height:48px;border-radius:14px;background:#182331;border:1px solid var(--line);display:grid;place-items:center;overflow:hidden;flex:0 0 auto}.server-icon img{width:100%;height:100%;object-fit:cover}.server-main{min-width:0;flex:1}.server-name{font-size:17px;font-weight:850;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.meta{color:var(--muted);font-size:13px;margin-top:4px}.counts{display:flex;gap:10px;flex-wrap:wrap;margin-top:13px;font-size:12px}.pill{border:1px solid var(--line);border-radius:999px;padding:5px 9px;background:#0b1118}.green{color:var(--green)}.red{color:var(--red)}.gold{color:var(--gold)}.flag-hero{position:relative;overflow:hidden;padding:24px}.flag-hero-bg{position:absolute;inset:0 0 0 48%;opacity:.13;background-size:cover;background-position:center}.flag-hero>*{position:relative;z-index:1}.flag-head{display:flex;align-items:center;gap:14px}.flag-logo{width:58px;height:58px;border-radius:16px;background:#172231;border:1px solid var(--line);display:grid;place-items:center;overflow:hidden;font-size:28px}.flag-logo img{width:100%;height:100%;object-fit:cover}.flag-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:21px}.flag-stat{border:1px solid var(--line);background:#0a1118cc;border-radius:15px;padding:15px}.flag-stat strong{font-size:26px}.progress{height:7px;background:#263240;border-radius:999px;overflow:hidden;margin-top:15px}.progress span{height:100%;display:block;background:linear-gradient(90deg,var(--green),var(--gold),var(--red))}.flag-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}.list-head{padding:17px 18px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between}.list{padding:8px}.flag-row{padding:10px;border-radius:13px;display:flex;justify-content:space-between;align-items:center;gap:12px;min-height:66px;border:1px solid transparent;transition:.18s background,.18s border-color,.18s transform}.flag-row:hover{background:#17212c;border-color:#26384b;transform:translateY(-1px)}.flag-ident{display:flex;align-items:center;gap:12px;min-width:0}.flag-thumb{width:46px;height:46px;border-radius:10px;object-fit:contain;background:#080d13;border:1px solid #2a3949;padding:3px;flex:0 0 46px}.flag-fallback{width:46px;height:46px;border-radius:10px;background:linear-gradient(145deg,#172536,#0b121a);border:1px solid #2a3949;display:grid;place-items:center;font-size:21px;flex:0 0 46px}.flag-name{font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.flag-state{font-size:11px;font-weight:900;letter-spacing:.05em}.owner{color:#b0c0d0;max-width:45%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:right}.empty{padding:28px;color:var(--muted);text-align:center}.docs{display:grid;grid-template-columns:240px 1fr;gap:20px;align-items:start}.toc{position:sticky;top:18px;padding:15px}.toc a{display:block;padding:9px 10px;color:#a8b9cb;border-radius:9px;font-size:14px}.toc a:hover{background:#17212c;color:#fff}.doc-body{padding:26px}.doc-body h2{margin-top:34px}.command{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:#c7dbef;background:#091019;border:1px solid #243244;padding:3px 7px;border-radius:7px}.status-box{padding:23px}.status-line{display:flex;justify-content:space-between;gap:15px;padding:12px 0;border-bottom:1px solid #202c39}.status-line:last-child{border:0}.footer{border-top:1px solid #1e2936;margin-top:60px;padding:28px 0 40px;color:#72859a;font-size:13px;display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}.user-card{display:flex;align-items:center;gap:12px}.user-avatar{width:44px;height:44px;border-radius:50%;border:1px solid var(--line);object-fit:cover}.dashboard-head{display:flex;justify-content:space-between;gap:20px;align-items:center;flex-wrap:wrap}.notice{padding:16px 18px;border:1px solid var(--line);background:#101822;border-radius:14px;color:#b8c7d8}.private-badge{display:inline-flex;align-items:center;gap:7px;color:#b9c9db;font-size:12px;font-weight:800;border:1px solid var(--line);padding:6px 10px;border-radius:999px;background:#0b121a}.hidden{display:none!important}.manage-shell{display:grid;grid-template-columns:280px 1fr;gap:18px;align-items:start}.manage-side{position:sticky;top:18px;padding:16px}.manage-side a{display:block;padding:10px 11px;border-radius:10px;color:#b8c8d9;font-size:14px}.manage-side a:hover{background:#17212c;color:#fff}.tool-stack{display:grid;gap:14px}.tool-card{padding:22px}.tool-card h3{margin:0 0 7px}.tool-card p{margin:0 0 16px;color:var(--muted);line-height:1.5}.form-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:11px}.field{display:grid;gap:6px}.field.full{grid-column:1/-1}.field label{font-size:12px;color:#aebed0;font-weight:800;letter-spacing:.04em;text-transform:uppercase}.input,.select{width:100%;padding:12px 13px;border-radius:11px;border:1px solid var(--line);background:#0b1219;color:#fff;outline:none;font-size:14px}.input:focus,.select:focus{border-color:#5c7fa5}.danger-btn{background:#35131b;border-color:#6d2637;color:#ff9caf}.danger-btn:hover{background:#431821;border-color:#974055}.result{margin-top:13px;padding:13px;border:1px solid var(--line);border-radius:12px;background:#0b1219;color:#c8d5e2;white-space:pre-wrap;word-break:break-word;display:none}.result.show{display:block}.setup-table{display:grid;gap:8px}.setup-row{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:13px;border:1px solid #22303f;border-radius:12px;background:#0b1118}.setup-row strong{display:block}.tiny{font-size:12px;color:var(--muted)}.toolbar{display:flex;gap:9px;flex-wrap:wrap}.role-note{font-size:12px;color:var(--muted);margin-top:6px}.spinner{opacity:.65;pointer-events:none}.web-command{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:#89bfff;font-size:12px}.guild-control-card{padding:20px;display:flex;gap:15px;align-items:center}.guild-control-card .server-main{flex:1}
.portal-head{display:flex;align-items:center;justify-content:space-between;gap:18px;margin:18px 0 24px}.portal-server{display:flex;align-items:center;gap:14px;min-width:0}.portal-server h1{font-size:clamp(30px,5vw,48px);letter-spacing:-1.5px;margin:0}.portal-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0 24px}.portal-tab{padding:10px 13px;border:1px solid var(--line);border-radius:11px;color:#aebed0;background:#101720;font-size:13px;font-weight:800}.portal-tab:hover,.portal-tab.active{color:#fff;border-color:#4c6680;background:#172331}.portal-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.portal-card{padding:24px;display:flex;flex-direction:column;min-height:220px}.portal-card .portal-icon{font-size:30px;margin-bottom:14px}.portal-card h3{font-size:21px;margin:0 0 8px}.portal-card p{color:var(--muted);line-height:1.6;margin:0 0 18px}.portal-card .portal-actions{margin-top:auto;display:flex;gap:9px;flex-wrap:wrap}.portal-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:18px 0 24px}.portal-kpi{padding:16px;border:1px solid var(--line);border-radius:15px;background:#0e151d}.portal-kpi strong{display:block;font-size:25px}.portal-kpi span{font-size:12px;color:var(--muted)}.tool-page{display:grid;gap:14px;max-width:920px}.section-label{font-size:12px;font-weight:900;letter-spacing:.08em;text-transform:uppercase;color:#83baff}.coming-soon{border-style:dashed;opacity:.78}.command-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.subnav-note{color:var(--muted);font-size:13px;line-height:1.55}.status-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.status-card{padding:22px}.status-card strong{display:block;font-size:28px;margin-top:8px}
@media(max-width:900px){.portal-grid,.command-grid,.status-grid{grid-template-columns:1fr}.portal-kpis{grid-template-columns:1fr 1fr}.manage-shell{grid-template-columns:1fr}.manage-side{position:static}.form-grid{grid-template-columns:1fr}.field.full{grid-column:auto}}@media(max-width:900px){.hero-home{grid-template-columns:1fr;padding-top:45px}.mock{transform:none}.feature-grid{grid-template-columns:1fr 1fr}.stat-band{grid-template-columns:1fr 1fr}.server-grid{grid-template-columns:1fr}.docs{grid-template-columns:1fr}.toc{position:static}.flag-grid{grid-template-columns:1fr}}@media(max-width:620px){.nav{height:auto;padding:14px 0;align-items:flex-start}.navlinks a:not(.keep){display:none}.hero-home{padding-top:34px}.feature-grid{grid-template-columns:1fr}.flag-stats{grid-template-columns:1fr 1fr 1fr}.flag-stat{padding:11px}.flag-stat strong{font-size:21px}.wrap{width:min(100% - 22px,1180px)}h1{letter-spacing:-2px}.stat-band{grid-template-columns:1fr 1fr}}
"""


def _nav(invite_url: str | None = None) -> str:
    invite = f'<a class="btn primary keep" href="{html.escape(invite_url)}">Add to Discord</a>' if invite_url else ""
    return f"""
<nav class="nav wrap">
  <a class="brand" href="/"><span class="brandmark">🚩</span><span>DayZ Manager</span></a>
  <div class="navlinks">
    <a href="/servers">Managed Servers</a>
    <a href="/dashboard">My Dashboard</a>
    <a href="/docs">Docs</a>
    <a href="/status">Status</a>
    {invite}
  </div>
</nav>"""


def _footer() -> str:
    return '<footer class="footer wrap"><span>© DayZ Manager • Built for the DayZ community.</span><span>Live Discord + web flag management</span></footer>'


def _page(title: str, body: str, invite_url: str | None = None, description: str = "DayZ Manager") -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#090d12"><meta name="description" content="{html.escape(description)}"><title>{html.escape(title)}</title><style>{SITE_CSS}</style></head><body>{_nav(invite_url)}{body}{_footer()}</body></html>"""


def _invite_url(bot: commands.Bot) -> str | None:
    if not bot.user:
        return None
    permissions = discord.Permissions(
        manage_channels=True,
        manage_messages=True,
        view_channel=True,
        send_messages=True,
        read_message_history=True,
        embed_links=True,
    )
    query = urlencode({
        "client_id": str(bot.user.id),
        "permissions": str(permissions.value),
        "scope": "bot applications.commands",
    })
    return f"https://discord.com/oauth2/authorize?{query}"


# =========================================================
# ROUTES
# =========================================================

async def health(request: web.Request) -> web.Response:
    bot: commands.Bot = request.app["bot"]
    return web.json_response({
        "ok": True,
        "service": "dayz-manager",
        "discord_ready": bot.is_ready(),
        "guilds": len(bot.guilds),
    })


async def homepage(request: web.Request) -> web.Response:
    bot: commands.Bot = request.app["bot"]
    host = request.host.split(":", 1)[0].casefold()
    if host.startswith("flags."):
        raise web.HTTPFound("/flags")

    setups = await _public_setups(bot)
    total_flags = sum(x["total"] for x in setups)
    total_claimed = sum(x["claimed_count"] for x in setups)
    body = f"""
<main class="wrap">
  <section class="hero-home">
    <div>
      <span class="eyebrow"><span class="dot"></span> Live DayZ Discord management</span>
      <h1><span class="gradient">DayZ Manager</span><br>built for server owners.</h1>
      <p class="lead">Run a cleaner DayZ community with live faction flag tracking, administrator-controlled claims and releases, setup management, audit history, server utilities, and public web dashboards that stay synced with Discord.</p>
      <div class="hero-actions"><a class="btn primary" href="/dashboard">🔐 My Dashboard</a><a class="btn" href="/invite">➕ Add DayZ Manager</a><a class="btn" href="/servers">🚩 Managed Servers</a><a class="btn" href="/docs">📖 View Commands</a></div>
    </div>
    <div class="mock">
      <div class="mock-head"><strong>🚩 Live Flag Dashboard</strong><span class="green">● LIVE</span></div>
      <div class="mini-stat-grid"><div class="mini-stat"><strong class="green">21</strong><span class="meta">Available</span></div><div class="mini-stat"><strong class="red">6</strong><span class="meta">Claimed</span></div><div class="mini-stat"><strong class="gold">27</strong><span class="meta">Total</span></div></div>
      <div class="mini-list"><div class="mini-row"><span>🟢 APA</span><span class="green">AVAILABLE</span></div><div class="mini-row"><span>🔴 Wolf</span><span>Faction-HIVE</span></div><div class="mini-row"><span>🟢 NAPA</span><span class="green">AVAILABLE</span></div></div>
    </div>
  </section>
  <section class="section">
    <h2 class="section-title">One bot. One live control system.</h2><p class="section-sub">The Discord dashboard and public website read from the same PostgreSQL flag data, so players see current availability while administrators keep all management actions inside Discord.</p>
    <div class="stat-band"><div class="big-stat"><strong>{len(bot.guilds)}</strong><span>Discord servers connected</span></div><div class="big-stat"><strong>{len(setups)}</strong><span>Public flag setups</span></div><div class="big-stat"><strong>{total_flags}</strong><span>Flags tracked</span></div><div class="big-stat"><strong>{total_claimed}</strong><span>Flags currently claimed</span></div></div>
  </section>
  <section class="section">
    <h2 class="section-title">Built around the way DayZ communities operate.</h2>
    <div class="feature-grid">
      <div class="feature"><div class="icon">🚩</div><h3>Live Flag Management</h3><p>Available and claimed flags stay synchronized between the Components V2 Discord dashboard and public web portal.</p></div>
      <div class="feature"><div class="icon">🔐</div><h3>Administrator Controlled</h3><p>Claim and release actions stay administrator-only in both Discord and the private website dashboard. Faction roles identify owners; they never grant management permission.</p></div>
      <div class="feature"><div class="icon">🕘</div><h3>Audit History</h3><p>See which flag changed, which faction owned it, who performed the action, and when it happened.</p></div>
      <div class="feature"><div class="icon">🗺️</div><h3>Map Ready</h3><p>Support for Chernarus, Livonia, Sakhal, and Nasdara is built into the Flag System.</p></div>
      <div class="feature"><div class="icon">⚙️</div><h3>Self-Service Setups</h3><p>Server administrators can view, refresh, inspect, and delete their own server's Flag System setups.</p></div>
      <div class="feature"><div class="icon">🌐</div><h3>Public Live Pages</h3><p>Give players a clean link to check flag availability without needing to dig through Discord interactions.</p></div>
    </div>
  </section>
  <section class="section"><div class="card" style="padding:30px;text-align:center"><h2 class="section-title">Ready to see it live?</h2><p class="section-sub" style="margin:0 auto 22px">Browse DayZ communities using DayZ Manager, then open that server to view its live Flag Systems.</p><a class="btn primary" href="/servers">Browse Managed Servers →</a></div></section>
</main>"""
    return web.Response(text=_page("DayZ Manager — DayZ Discord Management", body, _invite_url(bot), "DayZ Manager is a Discord management platform for DayZ communities with live faction flag tracking and public web dashboards."), content_type="text/html", headers={"Cache-Control": "no-store"})


async def discord_login(request: web.Request) -> web.StreamResponse:
    bot: commands.Bot = request.app["bot"]
    client_id = _oauth_client_id(bot)
    client_secret = _oauth_client_secret()
    redirect_uri = _oauth_redirect_uri()
    if not client_id or not client_secret or not redirect_uri:
        return web.Response(
            text=_page(
                "Discord Login Not Configured — DayZ Manager",
                '<main class="wrap"><section class="section"><div class="card empty"><h2>🔐 Discord login is not configured yet.</h2><p>Add DISCORD_CLIENT_SECRET on Railway and register the OAuth redirect URL in the Discord Developer Portal.</p></div></section></main>',
                _invite_url(bot),
            ),
            content_type="text/html",
            status=503,
        )

    _prune_web_auth()
    state = secrets.token_urlsafe(32)
    OAUTH_STATES[state] = time.time() + STATE_TTL
    query = urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": "identify guilds",
        "state": state,
    })
    response = web.HTTPFound(f"{DISCORD_OAUTH_AUTHORIZE}?{query}")
    response.set_cookie(
        STATE_COOKIE,
        state,
        max_age=STATE_TTL,
        httponly=True,
        secure=True,
        samesite="Lax",
        path="/",
    )
    raise response


async def discord_callback(request: web.Request) -> web.StreamResponse:
    bot: commands.Bot = request.app["bot"]
    state = request.query.get("state", "")
    code = request.query.get("code", "")
    expected = request.cookies.get(STATE_COOKIE, "")
    _prune_web_auth()
    state_exists = OAUTH_STATES.pop(state, None) if state else None
    valid_state = bool(
        state
        and expected
        and state_exists
        and secrets.compare_digest(state, expected)
    )
    if not valid_state or not code:
        raise web.HTTPBadRequest(text="Invalid or expired Discord OAuth state.")

    client_id = _oauth_client_id(bot)
    client_secret = _oauth_client_secret()
    redirect_uri = _oauth_redirect_uri()
    if not client_id or not client_secret or not redirect_uri:
        raise web.HTTPServiceUnavailable(text="Discord OAuth is not configured.")

    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as client:
        async with client.post(
            DISCORD_OAUTH_TOKEN,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        ) as token_response:
            token_data = await token_response.json(content_type=None)
            if token_response.status != 200 or not token_data.get("access_token"):
                log.warning("Discord OAuth token exchange failed | status=%s", token_response.status)
                raise web.HTTPBadGateway(text="Discord login failed during token exchange.")

        access_token = token_data["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}
        async with client.get(f"{DISCORD_API}/users/@me", headers=headers) as user_response:
            user = await user_response.json(content_type=None)
            if user_response.status != 200:
                raise web.HTTPBadGateway(text="Discord login failed while reading your profile.")
        async with client.get(f"{DISCORD_API}/users/@me/guilds", headers=headers) as guild_response:
            guilds = await guild_response.json(content_type=None)
            if guild_response.status != 200 or not isinstance(guilds, list):
                raise web.HTTPBadGateway(text="Discord login failed while reading your servers.")

    admin_guilds = {
        str(guild["id"])
        for guild in guilds
        if guild.get("id") and _can_admin_oauth_guild(guild)
    }
    session_id = secrets.token_urlsafe(40)
    WEB_SESSIONS[session_id] = {
        "user": {
            "id": str(user.get("id") or ""),
            "username": str(user.get("global_name") or user.get("username") or "Discord User"),
            "avatar_url": _discord_avatar_url(user),
        },
        "guild_ids": sorted(admin_guilds),
        "csrf_token": secrets.token_urlsafe(32),
        "expires_at": time.time() + SESSION_TTL,
    }

    response = web.HTTPFound("/dashboard")
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        max_age=SESSION_TTL,
        httponly=True,
        secure=True,
        samesite="Lax",
        path="/",
    )
    response.del_cookie(STATE_COOKIE, path="/")
    raise response


async def discord_logout(request: web.Request) -> web.StreamResponse:
    session_id = request.cookies.get(SESSION_COOKIE, "")
    if session_id:
        WEB_SESSIONS.pop(session_id, None)
    response = web.HTTPFound("/")
    response.del_cookie(SESSION_COOKIE, path="/")
    raise response


async def dashboard_page(request: web.Request) -> web.Response:
    bot: commands.Bot = request.app["bot"]
    session = _current_session(request)
    if not session:
        body = """
<main class="wrap"><section class="section" style="padding-top:60px"><div class="card" style="padding:34px;max-width:720px;margin:auto;text-align:center"><span class="private-badge">🔐 PRIVATE SERVER-OWNER AREA</span><h1 style="font-size:clamp(36px,6vw,58px)">Your DayZ Manager <span class="gradient">Dashboard</span></h1><p class="lead" style="margin:0 auto 24px">Sign in with Discord. DayZ Manager will only show servers you own or where you have Administrator permission.</p><a class="btn primary" href="/auth/discord">Login with Discord</a><p class="meta" style="margin-top:18px">Requested scopes: identify + guilds. Management access is checked against your Discord permissions.</p></div></section></main>"""
        return web.Response(text=_page("My Dashboard — DayZ Manager", body, _invite_url(bot)), content_type="text/html", headers={"Cache-Control": "no-store"})

    allowed = set(session.get("guild_ids", []))
    setups = await _public_setups(bot)
    setup_counts: dict[str, int] = {}
    for item in setups:
        if item["guild_id"] in allowed:
            setup_counts[item["guild_id"]] = setup_counts.get(item["guild_id"], 0) + 1

    guilds = [guild for guild in bot.guilds if str(guild.id) in allowed]
    guilds.sort(key=lambda g: g.name.casefold())
    user = session.get("user", {})
    avatar = user.get("avatar_url")
    avatar_html = f'<img class="user-avatar" src="{html.escape(avatar)}" alt="">' if avatar else '<span class="user-avatar" style="display:grid;place-items:center;background:#172231">👤</span>'

    cards = []
    for guild in guilds:
        icon = f'<img alt="" src="{html.escape(str(guild.icon.url))}">' if guild.icon else "🛡️"
        count = setup_counts.get(str(guild.id), 0)
        cards.append(
            f'<a class="card guild-control-card" href="/dashboard/{guild.id}">'
            f'<div class="server-icon">{icon}</div><div class="server-main">'
            f'<div class="server-name">{html.escape(guild.name)}</div>'
            f'<div class="meta">Discord server management</div>'
            f'<div class="counts"><span class="pill">🚩 {count} Flag Setup{"s" if count != 1 else ""}</span>'
            f'<span class="pill green">⚙️ Full Web Controls</span></div></div>'
            '<span style="color:#7f93a9">→</span></a>'
        )
    entries = "".join(cards) if cards else '<div class="card empty" style="grid-column:1/-1"><h3>No manageable servers found</h3><p>Your Discord account does not currently have an Owner/Administrator server in common with DayZ Manager.</p></div>'
    username = html.escape(str(user.get("username", "Discord User")))
    body = f"""
<main class="wrap"><section class="section" style="padding-top:45px">
<div class="dashboard-head"><div><span class="private-badge">🔐 PRIVATE DASHBOARD</span><h1 style="font-size:clamp(38px,6vw,64px);margin-bottom:10px">My <span class="gradient">Servers</span></h1><p class="section-sub">Choose a Discord server to open its complete DayZ Manager control panel.</p></div><div class="user-card">{avatar_html}<div><strong>{username}</strong><div class="meta">{len(guilds)} manageable server(s)</div><a class="meta" href="/auth/logout">Sign out</a></div></div></div>
<div class="notice" style="margin:20px 0">🛡️ Every management request is re-scoped to your authenticated Discord server permissions. One server cannot modify another server's data.</div>
<div class="server-grid">{entries}</div>
</section></main>"""
    return web.Response(text=_page("My Servers — DayZ Manager", body, _invite_url(bot)), content_type="text/html", headers={"Cache-Control": "no-store"})


def _guild_portal_tabs(guild_id: int, active: str) -> str:
    items = [
        ("overview", f"/dashboard/{guild_id}", "🏠 Overview"),
        ("flags", f"/dashboard/{guild_id}/flags", "🚩 Flag System"),
        ("tools", f"/dashboard/{guild_id}/tools", "🛠️ Server Tools"),
        ("status", f"/dashboard/{guild_id}/status", "🤖 Bot Status"),
        ("live", f"/servers/{guild_id}", "🌐 Live Pages"),
    ]
    return '<div class="portal-tabs">' + ''.join(
        f'<a class="portal-tab{" active" if key == active else ""}" href="{url}">{label}</a>'
        for key, url, label in items
    ) + '</div>'


async def _guild_portal_context(request: web.Request) -> tuple[commands.Bot, dict, discord.Guild, list[dict]]:
    bot: commands.Bot = request.app["bot"]
    guild_id = request.match_info["guild_id"]
    session, guild = _authorized_web_guild(request, guild_id)
    if not session or not guild:
        if not _current_session(request):
            raise web.HTTPFound("/auth/discord")
        raise web.HTTPForbidden(text="You do not have permission to manage this Discord server.")

    sessions = await utils.get_guild_flag_setups(str(guild.id))
    setups: list[dict] = []
    for row in sessions:
        map_key = utils.normalize_map(row["map"])
        server = utils.normalize_server(row["server"])
        setups.append({
            "map": map_key,
            "map_name": utils.MAP_DATA.get(map_key, {}).get("name", map_key.title()),
            "server": server,
            "url": flag_page_url(guild.id, map_key, server),
        })
    setups.sort(key=lambda x: (x["map_name"].casefold(), x["server"].casefold()))
    return bot, session, guild, setups


def _guild_portal_header(guild: discord.Guild, active: str, subtitle: str) -> str:
    icon = f'<img alt="" src="{html.escape(str(guild.icon.url))}">' if guild.icon else "🛡️"
    return f"""
<a href="/dashboard" class="meta">← My Servers</a>
<div class="portal-head">
  <div class="portal-server">
    <div class="server-icon" style="width:62px;height:62px;font-size:28px">{icon}</div>
    <div><span class="private-badge">🔐 PRIVATE SERVER PORTAL</span><h1>{html.escape(guild.name)}</h1><div class="subnav-note">{html.escape(subtitle)}</div></div>
  </div>
</div>
{_guild_portal_tabs(guild.id, active)}
"""


async def guild_dashboard_page(request: web.Request) -> web.Response:
    bot, session, guild, setups = await _guild_portal_context(request)
    claimed = 0
    available = 0
    for setup in setups:
        rows = await utils.get_all_flags(str(guild.id), setup["map"], setup["server"])
        c = sum(1 for row in rows if row["role_id"] or row["status"] == "❌")
        claimed += c
        available += max(0, len(rows) - c)

    teleporter_enabled = guild.id in set(ALLOWED_GUILD_IDS)
    body = f"""
<main class="wrap"><section class="section" style="padding-top:32px">
{_guild_portal_header(guild, "overview", "Choose a section below. Tools are separated into focused pages so the portal stays clean as DayZ Manager grows.")}
<div class="portal-kpis">
  <div class="portal-kpi"><strong>{len(setups)}</strong><span>Flag System setups</span></div>
  <div class="portal-kpi"><strong class="green">{available}</strong><span>Available flags</span></div>
  <div class="portal-kpi"><strong class="red">{claimed}</strong><span>Claimed flags</span></div>
  <div class="portal-kpi"><strong>{"Enabled" if teleporter_enabled else "Restricted"}</strong><span>Server tools access</span></div>
</div>
<div class="portal-grid">
  <div class="card portal-card"><div class="portal-icon">🚩</div><h3>Flag System Tools</h3><p>Create and delete setups, assign and release flags, inspect status, refresh Discord dashboards, and review audit history.</p><div class="portal-actions"><a class="btn primary" href="/dashboard/{guild.id}/flags">Open Flag System →</a><a class="btn" href="/servers/{guild.id}">Public Flag Pages</a></div></div>
  <div class="card portal-card"><div class="portal-icon">🛠️</div><h3>Server Tools</h3><p>DayZ utilities live here separately from the Flag System. Your Teleporter Generator is here now, with room for more server tools later.</p><div class="portal-actions"><a class="btn primary" href="/dashboard/{guild.id}/tools">Open Server Tools →</a></div></div>
  <div class="card portal-card"><div class="portal-icon">🤖</div><h3>Bot & Connection Status</h3><p>Check DayZ Manager's Discord connection, PostgreSQL health, latency, uptime, connected guild count, and registered commands.</p><div class="portal-actions"><a class="btn" href="/dashboard/{guild.id}/status">View Bot Status →</a></div></div>
  <div class="card portal-card"><div class="portal-icon">🌐</div><h3>Live Public Pages</h3><p>Open the public-facing pages players use to see available and claimed flags for this Discord community.</p><div class="portal-actions"><a class="btn" href="/servers/{guild.id}">View Live Pages →</a></div></div>
</div>
</section></main>"""
    return web.Response(text=_page(f"{guild.name} — Dashboard", body, _invite_url(bot), f"Private DayZ Manager dashboard for {guild.name}."), content_type="text/html", headers={"Cache-Control": "no-store"})


async def guild_flag_tools_page(request: web.Request) -> web.Response:
    bot, session, guild, setups = await _guild_portal_context(request)
    setup_json = json.dumps(setups).replace("<", "\\u003c")
    maps_json = json.dumps([{"key": key, "name": value["name"]} for key, value in utils.MAP_DATA.items()]).replace("<", "\\u003c")
    csrf = json.dumps(str(session.get("csrf_token") or ""))

    setup_list = "".join(
        f'<div class="setup-row"><div><strong>{html.escape(x["map_name"])} • {html.escape(x["server"])}</strong><div class="tiny">{html.escape(_setup_key(x["map"], x["server"]))}</div></div><a class="btn" href="{html.escape(x["url"] or "#")}">Live Page</a></div>'
        for x in setups
    ) or '<div class="empty">No Flag Systems yet. Use Create / Repair Setup below.</div>'

    body = f"""
<main class="wrap"><section class="section" style="padding-top:32px">
{_guild_portal_header(guild, "flags", "All Flag System management is grouped here. These controls mirror the Discord slash commands.")}
<div class="tool-page">
  <section class="card tool-card"><span class="section-label">Current Systems</span><h3>🗂️ Flag System Setups</h3><p>All Flag Systems configured for this Discord server.</p><div id="setupList" class="setup-table">{setup_list}</div></section>

  <div class="command-grid">
    <section class="card tool-card"><span class="web-command">/setup</span><h3>➕ Create / Repair Setup</h3><p>Create a new Flag System or repair its Discord dashboard.</p><form id="setupForm" class="form-grid"><div class="field"><label>Map</label><select class="select" name="map" id="setupMap" required></select></div><div class="field"><label>Server Name</label><input class="input" name="server" maxlength="50" placeholder="Server 1" required></div><div class="field full"><button class="btn primary" type="submit">Create / Repair</button></div></form><div class="result" id="setupResult"></div></section>

    <section class="card tool-card"><span class="web-command">/flagstatus</span><h3>📊 Flag Status</h3><p>Inspect counts, Discord channel/message health, and missing faction roles.</p><div class="field"><label>Setup</label><select class="select setup-select" id="statusSetup"></select></div><button class="btn" id="statusBtn" type="button" style="margin-top:12px">Check Status</button><div class="result" id="statusResult"></div></section>
  </div>

  <div class="command-grid">
    <section class="card tool-card"><span class="web-command">/assign</span><h3>🏴 Assign Flag</h3><p>Assign an available flag to a Discord role.</p><form id="assignForm" class="form-grid"><div class="field full"><label>Setup</label><select class="select setup-select" name="setup" required></select></div><div class="field"><label>Available Flag</label><select class="select" name="flag" id="assignFlag" required></select></div><div class="field"><label>Faction Role</label><select class="select" name="role_id" id="roleSelect" required><option>Loading roles…</option></select></div><div class="field full"><button class="btn primary" type="submit">Assign Flag</button></div></form><div class="result" id="assignResult"></div></section>

    <section class="card tool-card"><span class="web-command">/release</span><h3>🏳️ Release Flag</h3><p>Return a claimed flag to the available pool.</p><form id="releaseForm" class="form-grid"><div class="field full"><label>Setup</label><select class="select setup-select" name="setup" required></select></div><div class="field full"><label>Claimed Flag</label><select class="select" name="flag" id="releaseFlag" required></select></div><div class="field full"><button class="btn" type="submit">Release Flag</button></div></form><div class="result" id="releaseResult"></div></section>
  </div>

  <div class="command-grid">
    <section class="card tool-card"><span class="web-command">/flagrefresh</span><h3>🔄 Refresh Dashboard</h3><p>Force-refresh the public Components V2 dashboard in Discord.</p><div class="field"><label>Setup</label><select class="select setup-select" id="refreshSetup"></select></div><button class="btn" id="refreshBtn" type="button" style="margin-top:12px">Refresh Discord Dashboard</button><div class="result" id="refreshResult"></div></section>

    <section class="card tool-card"><span class="web-command">/flaghistory</span><h3>🕘 Flag History</h3><p>Review recent claims and releases.</p><div class="form-grid"><div class="field"><label>Setup</label><select class="select setup-select" id="historySetup"></select></div><div class="field"><label>Entries</label><select class="select" id="historyLimit"><option>5</option><option selected>10</option><option>20</option></select></div></div><button class="btn" id="historyBtn" type="button" style="margin-top:12px">Load History</button><div class="result" id="historyResult"></div></section>
  </div>

  <section class="card tool-card"><span class="section-label">Website Management</span><h3>✏️ Rename Flag System</h3><p>Change an existing Flag System name without losing claims or history. DayZ Manager will also rename its Discord category/channel and refresh the live dashboard.</p><form id="renameForm" class="form-grid"><div class="field"><label>Existing Setup</label><select class="select setup-select" name="setup" required></select></div><div class="field"><label>New Setup Name</label><input class="input" name="new_server" maxlength="50" placeholder="Example: Server 2" required></div><div class="field full"><button class="btn primary" type="submit">Rename Flag System</button></div></form><div class="result" id="renameResult"></div></section>

  <section class="card tool-card"><span class="web-command">/deletesetup</span><h3>🗑️ Delete Flag System</h3><p>Permanently remove a setup. You can also delete its Discord channel and empty setup category.</p><form id="deleteForm" class="form-grid"><div class="field"><label>Setup</label><select class="select setup-select" name="setup" required></select></div><div class="field"><label>Discord Cleanup</label><label style="padding:12px;border:1px solid var(--line);border-radius:11px"><input type="checkbox" name="delete_channel" checked> Delete Discord flag channel too</label></div><div class="field full"><button class="btn danger-btn" type="submit">Delete Setup Permanently</button></div></form><div class="result" id="deleteResult"></div></section>
</div>
</section></main>
<script>
const GUILD={json.dumps(str(guild.id))},CSRF={csrf},MAPS={maps_json};
let SETUPS={setup_json},ROLES=[];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
const key=s=>s.map+'::'+s.server;
const unpack=v=>{{const i=v.indexOf('::');return {{map:v.slice(0,i),server:v.slice(i+2)}}}};
const show=(id,msg,ok=true)=>{{const e=document.getElementById(id);e.textContent=msg;e.classList.add('show');e.style.borderColor=ok?'#285642':'#6d2637'}};
async function api(path,opt={{}}){{opt.headers=Object.assign({{'X-CSRF-Token':CSRF}},opt.headers||{{}});const r=await fetch('/api/manage/'+encodeURIComponent(GUILD)+path,opt);let d;try{{d=await r.json()}}catch{{d={{error:await r.text()}}}}if(!r.ok)throw new Error(d.error||('HTTP '+r.status));return d}}
function fillMaps(){{document.getElementById('setupMap').innerHTML=MAPS.map(m=>'<option value="'+esc(m.key)+'">'+esc(m.name)+'</option>').join('')}}
function fillSetups(){{const options=SETUPS.length?SETUPS.map(s=>'<option value="'+esc(key(s))+'">'+esc(s.map_name+' • '+s.server)+'</option>').join(''):'<option value="">No setups yet</option>';document.querySelectorAll('.setup-select').forEach(el=>el.innerHTML=options);updateFlagChoices()}}
function renderSetups(){{document.getElementById('setupList').innerHTML=SETUPS.length?SETUPS.map(s=>'<div class="setup-row"><div><strong>'+esc(s.map_name+' • '+s.server)+'</strong><div class="tiny">'+esc(key(s))+'</div></div><a class="btn" href="'+esc(s.url||'#')+'">Live Page</a></div>').join(''):'<div class="empty">No Flag Systems yet. Use Create / Repair Setup below.</div>'}}
async function loadState(){{try{{const d=await api('/state');SETUPS=d.setups;ROLES=d.roles;fillSetups();renderSetups();document.getElementById('roleSelect').innerHTML=ROLES.length?ROLES.map(r=>'<option value="'+esc(r.id)+'">'+esc(r.name)+'</option>').join(''):'<option value="">No assignable roles found</option>'}}catch(err){{console.error('DayZ Manager state load failed:',err);document.getElementById('roleSelect').innerHTML='<option value="">Unable to load roles</option>';const list=document.getElementById('setupList');if(list)list.innerHTML='<div class="empty">⚠️ Unable to load setups: '+esc(err.message)+'</div>';}}}}
async function updateFlagChoices(){{try{{const ae=document.querySelector('#assignForm .setup-select');if(ae&&ae.value){{const s=unpack(ae.value),d=await api('/flags?map='+encodeURIComponent(s.map)+'&server='+encodeURIComponent(s.server));document.getElementById('assignFlag').innerHTML=d.available.map(x=>'<option value="'+esc(x.flag)+'">'+esc(x.flag)+'</option>').join('')||'<option value="">No available flags</option>'}}const re=document.querySelector('#releaseForm .setup-select');if(re&&re.value){{const s=unpack(re.value),d=await api('/flags?map='+encodeURIComponent(s.map)+'&server='+encodeURIComponent(s.server));document.getElementById('releaseFlag').innerHTML=d.claimed.map(x=>'<option value="'+esc(x.flag)+'">'+esc(x.flag+' — '+x.role_name)+'</option>').join('')||'<option value="">No claimed flags</option>'}}}}catch(e){{}}}}
document.addEventListener('change',e=>{{if(e.target.classList.contains('setup-select'))updateFlagChoices()}});
document.getElementById('setupForm').onsubmit=async e=>{{e.preventDefault();try{{const f=new FormData(e.target),d=await api('/setup',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(Object.fromEntries(f))}});show('setupResult',d.message);await loadState()}}catch(x){{show('setupResult',x.message,false)}}}};
document.getElementById('assignForm').onsubmit=async e=>{{e.preventDefault();try{{const f=new FormData(e.target),s=unpack(f.get('setup')),d=await api('/assign',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{...s,flag:f.get('flag'),role_id:f.get('role_id')}})}});show('assignResult',d.message);await loadState()}}catch(x){{show('assignResult',x.message,false)}}}};
document.getElementById('releaseForm').onsubmit=async e=>{{e.preventDefault();try{{const f=new FormData(e.target),s=unpack(f.get('setup')),d=await api('/release',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{...s,flag:f.get('flag')}})}});show('releaseResult',d.message);await loadState()}}catch(x){{show('releaseResult',x.message,false)}}}};
document.getElementById('renameForm').onsubmit=async e=>{{e.preventDefault();const f=new FormData(e.target),old=unpack(f.get('setup')),newName=String(f.get('new_server')||'').trim();if(!newName)return show('renameResult','Enter a new setup name.',false);if(!confirm('Rename '+old.map+' • '+old.server+' to '+newName+'?'))return;try{{const d=await api('/rename-setup',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{...old,new_server:newName}})}});show('renameResult',d.message);e.target.reset();await loadState()}}catch(x){{show('renameResult',x.message,false)}}}};
document.getElementById('deleteForm').onsubmit=async e=>{{e.preventDefault();const f=new FormData(e.target),s=unpack(f.get('setup'));if(!confirm('Permanently delete '+s.map+' • '+s.server+'?'))return;try{{const d=await api('/delete-setup',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{...s,delete_channel:f.get('delete_channel')==='on'}})}});show('deleteResult',d.message);await loadState()}}catch(x){{show('deleteResult',x.message,false)}}}};
document.getElementById('statusBtn').onclick=async()=>{{try{{const s=unpack(document.getElementById('statusSetup').value),d=await api('/status?map='+encodeURIComponent(s.map)+'&server='+encodeURIComponent(s.server));show('statusResult',JSON.stringify(d,null,2))}}catch(x){{show('statusResult',x.message,false)}}}};
document.getElementById('refreshBtn').onclick=async()=>{{try{{const s=unpack(document.getElementById('refreshSetup').value),d=await api('/refresh',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(s)}});show('refreshResult',d.message)}}catch(x){{show('refreshResult',x.message,false)}}}};
document.getElementById('historyBtn').onclick=async()=>{{try{{const s=unpack(document.getElementById('historySetup').value),l=document.getElementById('historyLimit').value,d=await api('/history?map='+encodeURIComponent(s.map)+'&server='+encodeURIComponent(s.server)+'&limit='+l);show('historyResult',d.entries.length?d.entries.map(x=>x.when+' — '+x.flag+' '+x.action+' — '+x.role+' — '+x.actor).join('\\n'):'No history yet.')}}catch(x){{show('historyResult',x.message,false)}}}};
fillMaps();fillSetups();loadState();
</script>"""
    return web.Response(text=_page(f"{guild.name} — Flag System Tools", body, _invite_url(bot), f"Flag System tools for {guild.name}."), content_type="text/html", headers={"Cache-Control": "no-store"})


async def guild_server_tools_page(request: web.Request) -> web.Response:
    bot, session, guild, setups = await _guild_portal_context(request)
    csrf = json.dumps(str(session.get("csrf_token") or ""))
    enabled = guild.id in set(ALLOWED_GUILD_IDS)

    if enabled:
        teleporter = f"""
<section class="card tool-card">
  <span class="web-command">/teleporter</span><h3>🌀 Teleporter Generator</h3>
  <p>Generate both two-way DayZ teleporter JSON files from the website and download them together as a ZIP.</p>
  <form id="teleporterForm" class="form-grid">
    <div class="field"><label>Faction Name</label><input class="input" name="faction_name" required></div>
    <div class="field"><label>Location A Name</label><input class="input" name="location_a_name" required></div>
    <div class="field"><label>Location B Name</label><input class="input" name="location_b_name" required></div>
    <div class="field"><label>Location A Coordinates</label><input class="input" name="location_a" placeholder="1234,56,789" required></div>
    <div class="field"><label>Location B Coordinates</label><input class="input" name="location_b" placeholder="9876,54,321" required></div>
    <div class="field full"><button class="btn primary" type="submit">Generate Teleporter ZIP</button></div>
  </form><div class="result" id="teleporterResult"></div>
</section>
<script>
const GUILD={json.dumps(str(guild.id))},CSRF={csrf};
const show=(id,msg,ok=true)=>{{const e=document.getElementById(id);e.textContent=msg;e.classList.add('show');e.style.borderColor=ok?'#285642':'#6d2637'}};
document.getElementById('teleporterForm').onsubmit=async e=>{{e.preventDefault();try{{const f=new FormData(e.target),r=await fetch('/api/manage/'+encodeURIComponent(GUILD)+'/teleporter',{{method:'POST',headers:{{'X-CSRF-Token':CSRF,'Content-Type':'application/json'}},body:JSON.stringify(Object.fromEntries(f))}});if(!r.ok){{let d;try{{d=await r.json()}}catch{{d={{error:'Generation failed'}}}}throw new Error(d.error)}}const blob=await r.blob(),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='DayZ_Manager_Teleporters.zip';a.click();URL.revokeObjectURL(a.href);show('teleporterResult','✅ Generated both teleporter JSON files.')}}catch(x){{show('teleporterResult',x.message,false)}}}};
</script>"""
    else:
        teleporter = """
<section class="card tool-card">
  <span class="web-command">/teleporter</span><h3>🌀 Teleporter Generator</h3>
  <p>This utility is restricted to approved Discord servers, matching the existing Discord command restriction.</p>
  <div class="notice">🔒 Teleporter Generator is not enabled for this Discord server.</div>
</section>"""

    body = f"""
<main class="wrap"><section class="section" style="padding-top:32px">
{_guild_portal_header(guild, "tools", "DayZ utilities that are separate from the Flag System live here.")}
<div class="tool-page">
  {teleporter}
  <section class="card tool-card coming-soon"><span class="section-label">Future Expansion</span><h3>🧰 More Server Tools</h3><p>This page is now the home for future DayZ utilities—vehicle/config generators, restart tools, map utilities, converters, and other server-owner tools can be added here without cluttering the Flag System.</p></section>
</div>
</section></main>"""
    return web.Response(text=_page(f"{guild.name} — Server Tools", body, _invite_url(bot), f"DayZ server tools for {guild.name}."), content_type="text/html", headers={"Cache-Control": "no-store"})


async def guild_status_page(request: web.Request) -> web.Response:
    bot, session, guild, setups = await _guild_portal_context(request)
    csrf = json.dumps(str(session.get("csrf_token") or ""))
    body = f"""
<main class="wrap"><section class="section" style="padding-top:32px">
{_guild_portal_header(guild, "status", "Health and connectivity for the DayZ Manager service.")}
<div class="status-grid" id="statusGrid">
  <div class="card status-card"><span class="meta">Discord</span><strong id="sDiscord">Loading…</strong></div>
  <div class="card status-card"><span class="meta">Database</span><strong id="sDatabase">Loading…</strong></div>
  <div class="card status-card"><span class="meta">Latency</span><strong id="sLatency">—</strong></div>
  <div class="card status-card"><span class="meta">Uptime</span><strong id="sUptime">—</strong></div>
  <div class="card status-card"><span class="meta">Connected Servers</span><strong id="sGuilds">—</strong></div>
  <div class="card status-card"><span class="meta">Slash Commands</span><strong id="sCommands">—</strong></div>
</div>
<div class="hero-actions"><button class="btn primary" id="refreshStatus">Refresh Status</button><a class="btn" href="/status">Public Status Page</a></div>
</section></main>
<script>
const GUILD={json.dumps(str(guild.id))};
async function loadStatus(){{const r=await fetch('/api/manage/'+encodeURIComponent(GUILD)+'/botstatus');const d=await r.json();if(!r.ok)throw new Error(d.error||'Status unavailable');document.getElementById('sDiscord').textContent=d.discord;document.getElementById('sDatabase').textContent=d.database;document.getElementById('sLatency').textContent=d.latency_ms+' ms';document.getElementById('sUptime').textContent=d.uptime;document.getElementById('sGuilds').textContent=d.guilds;document.getElementById('sCommands').textContent=d.commands;}}
document.getElementById('refreshStatus').onclick=()=>loadStatus().catch(alert);loadStatus().catch(alert);
</script>"""
    return web.Response(text=_page(f"{guild.name} — Bot Status", body, _invite_url(bot), f"DayZ Manager status for {guild.name}."), content_type="text/html", headers={"Cache-Control": "no-store"})




async def manage_state_api(request: web.Request) -> web.Response:
    bot: commands.Bot = request.app["bot"]
    guild_id = request.match_info["guild_id"]
    session, guild = _authorized_web_guild(request, guild_id)
    if not session or not guild:
        return web.json_response({"error": "Administrator access required."}, status=403)
    sessions = await utils.get_guild_flag_setups(str(guild.id))
    setups = []
    for row in sessions:
        map_key = utils.normalize_map(row["map"])
        server = utils.normalize_server(row["server"])
        setups.append({
            "map": map_key,
            "map_name": utils.MAP_DATA.get(map_key, {}).get("name", map_key.title()),
            "server": server,
            "url": flag_page_url(guild.id, map_key, server),
        })
    setups.sort(key=lambda x: (x["map_name"].casefold(), x["server"].casefold()))
    # Fetch roles directly from Discord so the web dashboard does not depend
    # on an incomplete/stale local role cache.
    try:
        discord_roles = await guild.fetch_roles()
    except (discord.Forbidden, discord.HTTPException):
        discord_roles = list(guild.roles)

    roles = [
        {"id": str(role.id), "name": role.name}
        for role in sorted(discord_roles, key=lambda r: r.position, reverse=True)
        if not role.is_default() and not role.managed
    ]

    return web.json_response({
        "guild_id": str(guild.id),
        "guild_name": guild.name,
        "setups": setups,
        "roles": roles,
        "teleporter_enabled": guild.id in set(ALLOWED_GUILD_IDS),
    })


async def manage_flags_api(request: web.Request) -> web.Response:
    bot: commands.Bot = request.app["bot"]
    guild_id = request.match_info["guild_id"]
    session, guild = _authorized_web_guild(request, guild_id)
    if not session or not guild:
        return web.json_response({"error": "Administrator access required."}, status=403)
    map_key = utils.normalize_map(request.query.get("map", ""))
    server = utils.normalize_server(request.query.get("server", ""))
    payload = await _get_payload(bot, str(guild.id), map_key, server)
    if not payload:
        return web.json_response({"error": "Flag setup not found."}, status=404)
    return web.json_response({"available": payload["available"], "claimed": payload["claimed"]})


async def manage_setup_api(request: web.Request) -> web.Response:
    from cogs.ui.flag_views import FlagManageView
    bot: commands.Bot = request.app["bot"]
    guild_id = request.match_info["guild_id"]
    session, guild = _authorized_web_guild(request, guild_id)
    if not session or not guild:
        return web.json_response({"error": "Administrator access required."}, status=403)
    if not _require_csrf(request, session):
        return web.json_response({"error": "Invalid session security token. Refresh the page and try again."}, status=403)
    data = await _request_json(request)
    map_key = utils.normalize_map(data.get("map", ""))
    server = utils.normalize_server(data.get("server", ""))
    if map_key not in utils.MAP_DATA:
        return web.json_response({"error": "Invalid map."}, status=400)
    if not server or len(server) > 50:
        return web.json_response({"error": "Server name must be 1–50 characters."}, status=400)

    await utils.initialize_flags(str(guild.id), map_key, server)
    map_info = utils.MAP_DATA[map_key]
    setup_cog = bot.get_cog("Setup")
    if not setup_cog:
        return web.json_response({"error": "Setup service is not loaded."}, status=503)

    try:
        category = await setup_cog.get_or_create_category(guild, f"🌍 {map_info['name']} — {server}", "Flag System Setup from web dashboard")
        channel = await setup_cog.get_or_create_text_channel(
            guild, utils.channel_name_for(map_key, server), category,
            "Flag System Setup from web dashboard",
            f"📜 **{map_info['name']} Flag System Initialized**\n🖥️ Server: **{server}**",
        )
        view = await FlagManageView.create(guild, map_key, server, bot)
        stored = await utils.get_flag_message(str(guild.id), map_key, server)
        message = None
        if stored:
            old_channel = guild.get_channel(int(stored["channel_id"]))
            if isinstance(old_channel, discord.TextChannel):
                try:
                    message = await old_channel.fetch_message(int(stored["message_id"]))
                    if getattr(message.flags, "components_v2", False):
                        await message.edit(view=view)
                    else:
                        await message.delete()
                        message = None
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    message = None
        if message is None:
            message = await channel.send(view=view)
        await utils.save_flag_message(str(guild.id), map_key, server, str(message.channel.id), str(message.id))
        try:
            bot.add_view(view, message_id=message.id)
        except ValueError:
            pass
        return web.json_response({"ok": True, "message": f"✅ Setup ready: {map_info['name']} • {server} in #{channel.name}."})
    except discord.Forbidden:
        return web.json_response({"error": "DayZ Manager is missing Discord permissions required to create/manage the setup channel."}, status=403)
    except discord.HTTPException as exc:
        log.exception("Web setup Discord error | guild=%s", guild.id)
        return web.json_response({"error": f"Discord rejected the setup request: {exc}"}, status=502)


async def manage_assign_api(request: web.Request) -> web.Response:
    from cogs.ui.flag_views import FlagManageView
    bot: commands.Bot = request.app["bot"]
    guild_id = request.match_info["guild_id"]
    session, guild = _authorized_web_guild(request, guild_id)
    if not session or not guild:
        return web.json_response({"error": "Administrator access required."}, status=403)
    if not _require_csrf(request, session):
        return web.json_response({"error": "Invalid session security token."}, status=403)
    data = await _request_json(request)
    map_key, server = utils.normalize_map(data.get("map", "")), utils.normalize_server(data.get("server", ""))
    flag = utils.normalize_flag(data.get("flag", ""))
    try:
        role = guild.get_role(int(data.get("role_id", "0")))
    except (TypeError, ValueError):
        role = None
    if not flag:
        return web.json_response({"error": "Invalid flag."}, status=400)
    if not role or role.is_default() or role.managed:
        return web.json_response({"error": "That Discord role cannot own a flag."}, status=400)
    if not await utils.flag_session_exists(str(guild.id), map_key, server):
        return web.json_response({"error": "Flag setup not found."}, status=404)

    result = await utils.claim_flag(str(guild.id), map_key, server, flag, str(role.id), actor_id=str(session["user"]["id"]), source="web:/assign")
    if not result:
        return web.json_response({"error": "That flag is already claimed or unavailable."}, status=409)
    await FlagManageView.create(guild, map_key, server, bot)
    view = await FlagManageView.create(guild, map_key, server, bot)
    await view.refresh_message()
    return web.json_response({"ok": True, "message": f"✅ {flag} assigned to {role.name}."})


async def manage_release_api(request: web.Request) -> web.Response:
    from cogs.ui.flag_views import FlagManageView
    bot: commands.Bot = request.app["bot"]
    guild_id = request.match_info["guild_id"]
    session, guild = _authorized_web_guild(request, guild_id)
    if not session or not guild:
        return web.json_response({"error": "Administrator access required."}, status=403)
    if not _require_csrf(request, session):
        return web.json_response({"error": "Invalid session security token."}, status=403)
    data = await _request_json(request)
    map_key, server = utils.normalize_map(data.get("map", "")), utils.normalize_server(data.get("server", ""))
    flag = utils.normalize_flag(data.get("flag", ""))
    if not flag:
        return web.json_response({"error": "Invalid flag."}, status=400)
    if not await utils.flag_session_exists(str(guild.id), map_key, server):
        return web.json_response({"error": "Flag setup not found."}, status=404)
    result = await utils.release_flag(str(guild.id), map_key, server, flag, actor_id=str(session["user"]["id"]), source="web:/release")
    if not result:
        return web.json_response({"error": "That flag is already available or does not exist."}, status=409)
    view = await FlagManageView.create(guild, map_key, server, bot)
    await view.refresh_message()
    return web.json_response({"ok": True, "message": f"✅ {flag} released."})


async def manage_rename_setup_api(request: web.Request) -> web.Response:
    bot: commands.Bot = request.app["bot"]
    guild_id = request.match_info["guild_id"]
    session, guild = _authorized_web_guild(request, guild_id)
    if not session or not guild:
        return web.json_response({"error": "Administrator access required."}, status=403)
    if not _require_csrf(request, session):
        return web.json_response({"error": "Invalid session security token."}, status=403)

    data = await _request_json(request)
    map_key = utils.normalize_map(data.get("map", ""))
    old_server = utils.normalize_server(data.get("server", ""))
    new_server = utils.normalize_server(data.get("new_server", ""))

    if map_key not in utils.MAP_DATA:
        return web.json_response({"error": "Invalid map."}, status=400)
    if not old_server:
        return web.json_response({"error": "Select an existing Flag System."}, status=400)
    if not new_server or len(new_server) > 50:
        return web.json_response({"error": "New setup name must be 1–50 characters."}, status=400)
    if old_server == new_server:
        return web.json_response({"error": "The new setup name is the same as the current name."}, status=400)

    stored = await utils.get_flag_message(str(guild.id), map_key, old_server)
    channel = None
    category = None
    if stored:
        try:
            channel = guild.get_channel(int(stored["channel_id"]))
        except (TypeError, ValueError):
            channel = None
        if isinstance(channel, discord.TextChannel):
            category = channel.category

    try:
        counts = await utils.rename_flag_session(
            str(guild.id), map_key, old_server, new_server
        )
    except LookupError as exc:
        return web.json_response({"error": str(exc)}, status=404)
    except FileExistsError as exc:
        return web.json_response({"error": str(exc)}, status=409)
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=400)

    warnings = []
    map_name = utils.MAP_DATA[map_key]["name"]
    reason = f"DayZ Manager Flag System renamed by Discord user {session['user']['id']}"

    if isinstance(channel, discord.TextChannel):
        try:
            await channel.edit(name=utils.channel_name_for(map_key, new_server), reason=reason)
        except discord.Forbidden:
            warnings.append("I could not rename the Discord channel because Manage Channels permission is missing.")
        except discord.HTTPException:
            warnings.append("Discord returned an error while renaming the flag channel.")

    if category is not None:
        try:
            await category.edit(name=f"🌍 {map_name} — {new_server}", reason=reason)
        except discord.Forbidden:
            warnings.append("I could not rename the Discord category because Manage Channels permission is missing.")
        except discord.HTTPException:
            warnings.append("Discord returned an error while renaming the setup category.")

    # The database rename has already moved the stored message record, so refresh
    # using the new key to update the displayed server name and button identifiers.
    ok, refresh_note = await _refresh_flag_dashboard(bot, guild, map_key, new_server)
    if not ok:
        warnings.append(refresh_note)

    message = f"✅ Renamed {map_name} • {old_server} → {new_server}. Claims and history were preserved."
    if warnings:
        message += "\n⚠️ " + " ".join(warnings)
    return web.json_response({
        "ok": True,
        "message": message,
        "map": map_key,
        "old_server": old_server,
        "new_server": new_server,
        "url": flag_page_url(guild.id, map_key, new_server),
        "counts": counts,
        "warnings": warnings,
    })


async def manage_delete_setup_api(request: web.Request) -> web.Response:
    guild_id = request.match_info["guild_id"]
    session, guild = _authorized_web_guild(request, guild_id)
    if not session or not guild:
        return web.json_response({"error": "Administrator access required."}, status=403)
    if not _require_csrf(request, session):
        return web.json_response({"error": "Invalid session security token."}, status=403)
    data = await _request_json(request)
    map_key, server = utils.normalize_map(data.get("map", "")), utils.normalize_server(data.get("server", ""))
    if not await utils.flag_session_exists(str(guild.id), map_key, server):
        return web.json_response({"error": "Setup not found in this Discord server."}, status=404)
    stored = await utils.get_flag_message(str(guild.id), map_key, server)
    counts = await utils.delete_flag_session(str(guild.id), map_key, server)
    note = "Database setup removed."
    category_deleted = False
    if bool(data.get("delete_channel", True)) and stored:
        channel = guild.get_channel(int(stored["channel_id"]))
        if isinstance(channel, discord.TextChannel):
            category = channel.category
            setup_only = bool(category and len(category.channels) == 1 and category.channels[0].id == channel.id)
            try:
                await channel.delete(reason=f"DayZ Manager web setup deletion by Discord user {session['user']['id']}")
                note = "Database setup and Discord channel removed."
                if setup_only and category:
                    try:
                        await category.delete(reason="DayZ Manager removed empty setup category")
                        category_deleted = True
                    except (discord.Forbidden, discord.HTTPException):
                        pass
            except discord.Forbidden:
                note = "Database setup removed, but the bot lacks permission to delete the Discord channel."
            except discord.HTTPException:
                note = "Database setup removed, but Discord returned an error deleting the channel."
    return web.json_response({"ok": True, "message": f"🗑️ {map_key.title()} • {server} deleted. {note}" + (" Empty category also removed." if category_deleted else ""), "counts": counts})


async def manage_status_api(request: web.Request) -> web.Response:
    guild_id = request.match_info["guild_id"]
    session, guild = _authorized_web_guild(request, guild_id)
    if not session or not guild:
        return web.json_response({"error": "Administrator access required."}, status=403)
    map_key, server = utils.normalize_map(request.query.get("map", "")), utils.normalize_server(request.query.get("server", ""))
    flags = await utils.get_all_flags(str(guild.id), map_key, server)
    if not flags:
        return web.json_response({"error": "Flag setup not found."}, status=404)
    stored = await utils.get_flag_message(str(guild.id), map_key, server)
    claimed = [r for r in flags if r["status"] == "❌" and r["role_id"]]
    missing_roles = sum(1 for r in claimed if not guild.get_role(int(r["role_id"])))
    channel_state, message_state = "Not stored", "Not stored"
    if stored:
        channel = guild.get_channel(int(stored["channel_id"]))
        channel_state = f"#{channel.name}" if isinstance(channel, discord.TextChannel) else "Missing channel"
        if isinstance(channel, discord.TextChannel):
            try:
                await channel.fetch_message(int(stored["message_id"]))
                message_state = "Reachable"
            except discord.NotFound:
                message_state = "Missing message"
            except discord.Forbidden:
                message_state = "No permission"
            except discord.HTTPException:
                message_state = "Discord error"
    return web.json_response({
        "map": utils.MAP_DATA.get(map_key, {}).get("name", map_key.title()),
        "server": server,
        "available": len(flags) - len(claimed),
        "claimed": len(claimed),
        "total": len(flags),
        "channel": channel_state,
        "dashboard_message": message_state,
        "missing_roles": missing_roles,
    })


async def manage_refresh_api(request: web.Request) -> web.Response:
    bot: commands.Bot = request.app["bot"]
    guild_id = request.match_info["guild_id"]
    session, guild = _authorized_web_guild(request, guild_id)
    if not session or not guild:
        return web.json_response({"error": "Administrator access required."}, status=403)
    if not _require_csrf(request, session):
        return web.json_response({"error": "Invalid session security token."}, status=403)
    data = await _request_json(request)
    map_key, server = utils.normalize_map(data.get("map", "")), utils.normalize_server(data.get("server", ""))
    ok, message = await _refresh_flag_dashboard(bot, guild, map_key, server)
    return web.json_response({"ok": ok, "message": ("✅ " if ok else "⚠️ ") + message}, status=200 if ok else 404)


async def manage_history_api(request: web.Request) -> web.Response:
    guild_id = request.match_info["guild_id"]
    session, guild = _authorized_web_guild(request, guild_id)
    if not session or not guild:
        return web.json_response({"error": "Administrator access required."}, status=403)
    map_key, server = utils.normalize_map(request.query.get("map", "")), utils.normalize_server(request.query.get("server", ""))
    try:
        limit = max(1, min(20, int(request.query.get("limit", "10"))))
    except ValueError:
        limit = 10
    rows = await utils.get_flag_history(str(guild.id), map_key, server, limit)
    entries = []
    for row in rows:
        role_name = "No role"
        if row["role_id"]:
            try:
                role = guild.get_role(int(row["role_id"]))
                role_name = role.name if role else f"Missing role {row['role_id']}"
            except (TypeError, ValueError):
                role_name = "Unknown role"
        actor = str(row["actor_id"] or "Unknown")
        entries.append({
            "flag": str(row["flag"]),
            "action": str(row["action"]).title(),
            "role": role_name,
            "actor": actor,
            "when": row["created_at"].strftime("%Y-%m-%d %H:%M UTC"),
            "source": str(row["source"]),
        })
    return web.json_response({"entries": entries})


async def manage_botstatus_api(request: web.Request) -> web.Response:
    bot: commands.Bot = request.app["bot"]
    guild_id = request.match_info["guild_id"]
    session, guild = _authorized_web_guild(request, guild_id)
    if not session or not guild:
        return web.json_response({"error": "Administrator access required."}, status=403)
    db_ok = True
    try:
        pool = await utils.ensure_connection()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception:
        db_ok = False
    started_at = getattr(bot, "started_at", discord.utils.utcnow())
    uptime = discord.utils.utcnow() - started_at
    total_seconds = max(0, int(uptime.total_seconds()))
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    return web.json_response({
        "discord": "Connected" if bot.is_ready() else "Connecting",
        "database": "Healthy" if db_ok else "Unavailable",
        "latency_ms": round(bot.latency * 1000),
        "guilds": len(bot.guilds),
        "uptime": f"{days}d {hours}h {minutes}m",
        "commands": len(bot.tree.get_commands()),
    })


async def manage_teleporter_api(request: web.Request) -> web.StreamResponse:
    guild_id = request.match_info["guild_id"]
    session, guild = _authorized_web_guild(request, guild_id)
    if not session or not guild:
        return web.json_response({"error": "Administrator access required."}, status=403)
    if guild.id not in set(ALLOWED_GUILD_IDS):
        return web.json_response({"error": "The Teleporter tool is not enabled for this Discord server."}, status=403)
    if not _require_csrf(request, session):
        return web.json_response({"error": "Invalid session security token."}, status=403)
    data = await _request_json(request)
    try:
        pos_a = _normalize_position(data.get("location_a", ""))
        pos_b = _normalize_position(data.get("location_b", ""))
    except Exception:
        return web.json_response({"error": "Invalid coordinates. Use [1234,56,789] or 1234,56,789."}, status=400)

    faction = _clean_file_name(data.get("faction_name", ""))
    a_name = str(data.get("location_a_name", "")).strip()
    b_name = str(data.get("location_b_name", "")).strip()
    if not a_name or not b_name:
        return web.json_response({"error": "Both location names are required."}, status=400)
    a_clean, b_clean = _clean_file_name(a_name), _clean_file_name(b_name)
    file1 = f"Teleporter_{faction}_{a_clean}_to_{b_clean}.json"
    file2 = f"Teleporter_{faction}_{b_clean}_to_{a_clean}.json"
    teleporter1 = {"areaName":"RestrictedAreaWarheadStorage","PRABoxes":[[[1,1,1],[90,0,0],pos_a]],"safePositions3D":[pos_b],"_comment":f"{faction}: {a_name} → {b_name}"}
    teleporter2 = {"areaName":"RestrictedAreaWarheadStorage","PRABoxes":[[[1,1,1],[90,0,0],pos_b]],"safePositions3D":[pos_a],"_comment":f"{faction}: {b_name} → {a_name}"}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(file1, json.dumps(teleporter1, indent=2))
        archive.writestr(file2, json.dumps(teleporter2, indent=2))
    return web.Response(body=buf.getvalue(), content_type="application/zip", headers={"Content-Disposition": 'attachment; filename="DayZ_Manager_Teleporters.zip"', "Cache-Control": "no-store"})




async def my_setups_api(request: web.Request) -> web.Response:
    bot: commands.Bot = request.app["bot"]
    session = _current_session(request)
    if not session:
        return web.json_response({"error": "Authentication required."}, status=401)
    allowed = set(session.get("guild_ids", []))
    setups = [item for item in await _public_setups(bot) if item["guild_id"] in allowed]
    response = web.json_response({"setups": setups})
    response.headers["Cache-Control"] = "no-store"
    return response


async def setups_api(request: web.Request) -> web.Response:
    bot: commands.Bot = request.app["bot"]
    response = web.json_response({"setups": await _public_setups(bot)})
    response.headers["Cache-Control"] = "no-store"
    return response


async def flags_root_redirect(request: web.Request) -> web.StreamResponse:
    """Keep old /flags links working while /servers is the public server directory."""
    legacy_guild = request.query.get("guild", "").strip()
    legacy_map = request.query.get("map", "").strip()
    legacy_server = request.query.get("server", "").strip()
    if legacy_guild and legacy_map and legacy_server:
        clean = flag_page_url(legacy_guild, legacy_map, legacy_server)
        if clean:
            clean_path = clean.split("/flags/", 1)[-1]
            raise web.HTTPFound(f"/flags/{clean_path}")
    raise web.HTTPFound("/servers")


async def flags_directory(request: web.Request) -> web.Response:
    bot: commands.Bot = request.app["bot"]

    # Public /servers is the directory of Discord servers using DayZ Manager.
    # Individual flag setups are grouped under each server page.
    setups = await _public_setups(bot)
    grouped: dict[str, dict] = {}
    for item in setups:
        guild_id = item["guild_id"]
        group = grouped.setdefault(guild_id, {
            "guild_id": guild_id,
            "guild_name": item["guild_name"],
            "guild_icon": item["guild_icon"],
            "setups": [],
            "maps": set(),
        })
        group["setups"].append(item)
        group["maps"].add(item["map_name"])

    cards = []
    for group in sorted(grouped.values(), key=lambda g: g["guild_name"].casefold()):
        icon = f'<img alt="" src="{html.escape(group["guild_icon"])}">' if group["guild_icon"] else "🚩"
        setup_count = len(group["setups"])
        maps = " • ".join(sorted(group["maps"], key=str.casefold)) or "Flag System"
        search_text = f'{group["guild_name"]} {maps}'.casefold()
        plural = "s" if setup_count != 1 else ""
        cards.append(
            f'''<a class="card server-card server-entry" href="/servers/{quote(group['guild_id'], safe='')}" data-search="{html.escape(search_text)}">
<div class="server-icon">{icon}</div>
<div class="server-main">
  <div class="server-name">{html.escape(group['guild_name'])}</div>
  <div class="meta">{html.escape(maps)}</div>
  <div class="counts"><span class="pill">🚩 {setup_count} Flag System{plural}</span></div>
</div>
<span style="color:#7f93a9">→</span>
</a>'''
        )

    entries = "".join(cards) if cards else '<div class="card empty" style="grid-column:1/-1">No DayZ Manager Flag System servers are currently available.</div>'
    body = f'''
<main class="wrap"><section class="section" style="padding-top:45px">
<span class="eyebrow"><span class="dot"></span> DayZ Manager Community</span>
<h1 style="font-size:clamp(38px,6vw,64px)">Servers Using <span class="gradient">DayZ Manager</span></h1>
<p class="lead">Choose a DayZ community to view only that server's live Flag Systems. Individual map/server setups stay grouped under their Discord server.</p>
<div class="directory-tools"><input id="search" class="search" placeholder="Search Discord server or map..." autocomplete="off"></div>
<div id="serverGrid" class="server-grid">{entries}</div>
<div id="noResults" class="card empty hidden" style="margin-top:14px">No servers match your search.</div>
</section></main>
<script>const q=document.getElementById('search');const cards=[...document.querySelectorAll('.server-entry')];const none=document.getElementById('noResults');q.addEventListener('input',()=>{{const v=q.value.trim().toLowerCase();let shown=0;cards.forEach(c=>{{const ok=!v||c.dataset.search.includes(v);c.classList.toggle('hidden',!ok);if(ok)shown++}});none.classList.toggle('hidden',shown!==0)}});</script>'''
    return web.Response(
        text=_page("Servers Using DayZ Manager", body, _invite_url(bot), "Browse DayZ communities using DayZ Manager and open each server's live Flag Systems."),
        content_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


async def server_flag_systems_page(request: web.Request) -> web.Response:
    bot: commands.Bot = request.app["bot"]
    guild_id = request.match_info["guild_id"].strip()

    setups = [item for item in await _public_setups(bot) if item["guild_id"] == guild_id]
    if not setups:
        return web.Response(
            text=_page(
                "Server Not Found — DayZ Manager",
                '<main class="wrap"><section class="section"><div class="card empty"><h2>🚩 Server not found</h2><p>This server has no public Flag Systems or DayZ Manager is no longer connected to it.</p><a class="btn" href="/servers">← Servers Using DayZ Manager</a></div></section></main>',
                _invite_url(bot),
            ),
            content_type="text/html",
            status=404,
            headers={"Cache-Control": "no-store"},
        )

    first = setups[0]
    icon = f'<img alt="" src="{html.escape(first["guild_icon"])}">' if first["guild_icon"] else "🚩"
    cards = []
    for item in sorted(setups, key=lambda x: (x["map_name"].casefold(), x["server"].casefold())):
        url = item["url"] or "#"
        cards.append(
            f'''<a class="card server-card" href="{html.escape(url)}">
<div class="server-icon">🚩</div>
<div class="server-main">
  <div class="server-name">{html.escape(item['map_name'])} • {html.escape(item['server'])}</div>
  <div class="meta">Live Flag System</div>
  <div class="counts">
    <span class="pill green">🟢 {item['available_count']} Available</span>
    <span class="pill red">🔴 {item['claimed_count']} Claimed</span>
    <span class="pill">🏴 {item['total']} Total</span>
  </div>
</div>
<span style="color:#7f93a9">→</span>
</a>'''
        )

    body = f'''
<main class="wrap"><section class="section" style="padding-top:40px">
<a href="/servers" class="meta">← Servers Using DayZ Manager</a>
<div class="dashboard-head" style="margin-top:18px">
  <div>
    <span class="eyebrow"><span class="dot"></span> Live Flag Systems</span>
    <h1 style="font-size:clamp(36px,6vw,62px);margin-bottom:10px">{html.escape(first['guild_name'])}</h1>
    <p class="section-sub">All public Flag Systems belonging to this Discord server are shown below.</p>
  </div>
  <div class="server-icon" style="width:72px;height:72px;font-size:34px">{icon}</div>
</div>
<div class="stat-band" style="grid-template-columns:repeat(3,1fr);margin-bottom:24px">
  <div class="big-stat"><strong>{len(setups)}</strong><span>Flag Systems</span></div>
  <div class="big-stat"><strong class="green">{sum(x['available_count'] for x in setups)}</strong><span>Available Flags</span></div>
  <div class="big-stat"><strong class="red">{sum(x['claimed_count'] for x in setups)}</strong><span>Claimed Flags</span></div>
</div>
<div class="server-grid">{"".join(cards)}</div>
</section></main>'''
    return web.Response(
        text=_page(f"{first['guild_name']} — Flag Systems", body, _invite_url(bot), f"Live DayZ Manager Flag Systems for {first['guild_name']}."),
        content_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


async def flags_api(request: web.Request) -> web.Response:
    bot: commands.Bot = request.app["bot"]
    guild_id = request.query.get("guild", "").strip()
    map_key = request.query.get("map", "").strip()
    server = request.query.get("server", "").strip()
    if not guild_id or not map_key or not server:
        return web.json_response({"error": "Missing guild, map, or server."}, status=400)
    payload = await _get_payload(bot, guild_id, map_key, server)
    if not payload:
        return web.json_response({"error": "Flag setup not found."}, status=404)
    response = web.json_response(payload)
    response.headers["Cache-Control"] = "no-store"
    return response


async def clean_flags_api(request: web.Request) -> web.Response:
    bot: commands.Bot = request.app["bot"]
    guild_id = request.match_info["guild_id"]
    map_key = request.match_info["map_key"]
    server_slug = request.match_info["server_slug"]
    server = await _resolve_server_slug(guild_id, map_key, server_slug)
    if not server:
        return web.json_response({"error": "Flag setup not found."}, status=404)
    payload = await _get_payload(bot, guild_id, map_key, server)
    if not payload:
        return web.json_response({"error": "Flag setup not found."}, status=404)
    response = web.json_response(payload)
    response.headers["Cache-Control"] = "no-store"
    return response


async def legacy_flags_page(request: web.Request) -> web.StreamResponse:
    guild_id = request.query.get("guild", "").strip()
    map_key = request.query.get("map", "").strip()
    server = request.query.get("server", "").strip()
    if guild_id and map_key and server:
        target = flag_page_url(guild_id, map_key, server)
        if target:
            # Keep redirects on the same host when possible.
            path = target.split("/flags/", 1)[-1]
            raise web.HTTPFound(f"/flags/{path}")
    raise web.HTTPFound("/flags")


async def flag_detail_page(request: web.Request) -> web.Response:
    bot: commands.Bot = request.app["bot"]
    guild_id = request.match_info["guild_id"]
    map_key = request.match_info["map_key"]
    server_slug = request.match_info["server_slug"]
    server = await _resolve_server_slug(guild_id, map_key, server_slug)
    if not server:
        return web.Response(text=_page("Flag System Not Found", '<main class="wrap"><section class="section"><div class="card empty"><h2>🚩 Flag System not found</h2><p>This setup may have been removed or the link is invalid.</p><a class="btn" href="/servers">Browse Managed Servers</a></div></section></main>', _invite_url(bot)), content_type="text/html", status=404)
    payload = await _get_payload(bot, guild_id, map_key, server)
    if not payload:
        return web.Response(text=_page("Flag System Not Found", '<main class="wrap"><section class="section"><div class="card empty"><h2>🚩 Flag System not found</h2></div></section></main>', _invite_url(bot)), content_type="text/html", status=404)

    map_bg = html.escape(payload.get("map_image") or "")
    guild_icon = f'<img alt="Server icon" src="{html.escape(payload["guild_icon"])}">' if payload.get("guild_icon") else "🚩"
    api_path = f"/api/flags/{quote(guild_id, safe='')}/{quote(utils.normalize_map(map_key), safe='')}/{quote(_slug(server), safe='')}"
    initial_json = json.dumps(payload).replace("<", "\\u003c")
    body = f"""
<main class="wrap"><section class="section" style="padding-top:36px"><a href="/servers/{quote(guild_id, safe='')}" class="meta">← Server Flag Systems</a><section class="card flag-hero" style="margin-top:15px"><div class="flag-hero-bg" id="heroBg" style="background-image:url('{map_bg}')"></div><div class="flag-head"><div class="flag-logo" id="guildLogo">{guild_icon}</div><div><span class="eyebrow"><span class="dot"></span> Live from DayZ Manager</span><h2 id="guildName" style="font-size:clamp(25px,4vw,38px);margin:9px 0 3px">{html.escape(payload['guild_name'])}</h2><div class="meta"><span id="mapName">{html.escape(payload['map_name'])}</span> • <span id="serverName">{html.escape(payload['server'])}</span></div></div></div><div class="flag-stats"><div class="flag-stat"><strong class="green" id="availableCount">{payload['available_count']}</strong><div class="meta">Available</div></div><div class="flag-stat"><strong class="red" id="claimedCount">{payload['claimed_count']}</strong><div class="meta">Claimed</div></div><div class="flag-stat"><strong class="gold" id="totalCount">{payload['total']}</strong><div class="meta">Total Flags</div></div></div><div class="progress"><span id="progressBar" style="width:{payload['claimed_pct']}%"></span></div></section><div class="flag-grid"><section class="card"><div class="list-head"><strong class="green">🟢 Available Flags</strong><span class="pill" id="availableBadge">{payload['available_count']}</span></div><div class="list" id="availableList"></div></section><section class="card"><div class="list-head"><strong class="red">🔴 Claimed Flags</strong><span class="pill" id="claimedBadge">{payload['claimed_count']}</span></div><div class="list" id="claimedList"></div></section></div><div class="meta" style="display:flex;justify-content:space-between;gap:15px;margin:14px 3px"><span>Read-only public view • Management stays in Discord</span><span id="updatedAt">Connecting…</span></div></section></main>
<script>const API={json.dumps(api_path)};const INITIAL={initial_json};const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));function render(d){{document.getElementById('guildName').textContent=d.guild_name;document.getElementById('mapName').textContent=d.map_name;document.getElementById('serverName').textContent=d.server;document.getElementById('availableCount').textContent=d.available_count;document.getElementById('claimedCount').textContent=d.claimed_count;document.getElementById('totalCount').textContent=d.total;document.getElementById('availableBadge').textContent=d.available_count;document.getElementById('claimedBadge').textContent=d.claimed_count;document.getElementById('progressBar').style.width=d.claimed_pct+'%';document.getElementById('availableList').innerHTML=d.available.length?d.available.map(x=>'<div class="flag-row"><div class="flag-ident">'+(x.image?'<img class="flag-thumb" src="'+esc(x.image)+'" alt="'+esc(x.flag)+' flag" loading="lazy">':'<span class="flag-fallback">🚩</span>')+'<strong class="flag-name">'+esc(x.flag)+'</strong></div><span class="green flag-state">AVAILABLE</span></div>').join(''):'<div class="empty">No flags are currently available.</div>';document.getElementById('claimedList').innerHTML=d.claimed.length?d.claimed.map(x=>'<div class="flag-row"><div class="flag-ident">'+(x.image?'<img class="flag-thumb" src="'+esc(x.image)+'" alt="'+esc(x.flag)+' flag" loading="lazy">':'<span class="flag-fallback">🚩</span>')+'<strong class="flag-name">'+esc(x.flag)+'</strong></div><span class="owner"><span class="red flag-state">CLAIMED</span><br>'+esc(x.role_name)+'</span></div>').join(''):'<div class="empty">No flags are currently claimed.</div>';document.getElementById('updatedAt').textContent='Updated '+new Date().toLocaleTimeString()}}async function refresh(){{try{{const r=await fetch(API,{{cache:'no-store'}});if(!r.ok)throw new Error('HTTP '+r.status);render(await r.json())}}catch(e){{document.getElementById('updatedAt').textContent='Connection interrupted — retrying'}}}}render(INITIAL);setInterval(refresh,10000);</script>"""
    return web.Response(text=_page(f"{payload['guild_name']} — Live Flags", body, _invite_url(bot), f"Live available and claimed flags for {payload['guild_name']} — {payload['map_name']} {payload['server']}."), content_type="text/html", headers={"Cache-Control": "no-store"})


async def docs_page(request: web.Request) -> web.Response:
    bot: commands.Bot = request.app["bot"]
    body = """
<main class="wrap"><section class="section" style="padding-top:45px"><span class="eyebrow">📖 Documentation</span><h1 style="font-size:clamp(38px,6vw,64px)">DayZ Manager <span class="gradient">commands</span></h1><p class="lead">A quick guide for server owners and administrators using the current Flag System and utilities.</p><div class="docs"><aside class="card toc"><a href="#setup">Setup</a><a href="#flags">Flag Management</a><a href="#admin">Admin Tools</a><a href="#web">Live Website</a><a href="#utility">Utilities</a></aside><article class="card doc-body"><h2 id="setup">Flag System Setup</h2><p><span class="command">/setup</span> creates/configures a Flag System for a selected map and server.</p><p><span class="command">/setups</span> lists Flag System setups belonging to the current Discord server.</p><p><span class="command">/deletesetup</span> permanently removes one of the current Discord server's setups after confirmation.</p><h2 id="flags">Flag Management</h2><p><span class="command">/assign</span> assigns an available flag to a faction role. Administrator-only.</p><p><span class="command">/release</span> releases a claimed flag. Administrator-only.</p><p>The permanent Components V2 dashboard also provides Claim, Release, View Flags, Find Flag, History, Admin Panel, and Live Website controls.</p><h2 id="admin">Admin Tools</h2><p><span class="command">/flagstatus</span> checks a setup's health.</p><p><span class="command">/flagrefresh</span> manually refreshes or repairs a setup dashboard.</p><p><span class="command">/flaghistory</span> shows recent flag audit history.</p><p><span class="command">/botstatus</span> shows bot/database status and latency.</p><h2 id="web">Live Website</h2><p>Every active Flag System has a public read-only page showing available and claimed flags. Server owners and administrators can also use <span class="command">/dashboard</span> on the website to sign in with Discord and see only Flag Systems from servers they own/administer. The private web dashboard mirrors all current Discord commands, including claim/release management.</p><h2 id="utility">Utilities</h2><p><span class="command">/teleporter</span> generates DayZ teleporter configuration files.</p></article></div></section></main>"""
    return web.Response(text=_page("Documentation — DayZ Manager", body, _invite_url(bot)), content_type="text/html")


async def status_page(request: web.Request) -> web.Response:
    bot: commands.Bot = request.app["bot"]
    db_ok = True
    try:
        await utils.ensure_connection()
    except Exception:
        db_ok = False
    setups = await _public_setups(bot) if db_ok else []
    discord_state = "Operational" if bot.is_ready() else "Connecting"
    db_state = "Operational" if db_ok else "Degraded"
    body = f"""
<main class="wrap"><section class="section" style="padding-top:45px"><span class="eyebrow"><span class="dot"></span> Service status</span><h1 style="font-size:clamp(38px,6vw,64px)">DayZ Manager <span class="gradient">Status</span></h1><div class="card status-box"><div class="status-line"><span>Discord Gateway</span><strong class="{'green' if bot.is_ready() else 'gold'}">● {discord_state}</strong></div><div class="status-line"><span>PostgreSQL Database</span><strong class="{'green' if db_ok else 'red'}">● {db_state}</strong></div><div class="status-line"><span>Web Portal</span><strong class="green">● Operational</strong></div><div class="status-line"><span>Discord Servers</span><strong>{len(bot.guilds)}</strong></div><div class="status-line"><span>Public Flag Setups</span><strong>{len(setups)}</strong></div><div class="status-line"><span>Gateway Latency</span><strong>{round(bot.latency*1000)} ms</strong></div></div></section></main>"""
    return web.Response(text=_page("Status — DayZ Manager", body, _invite_url(bot)), content_type="text/html", headers={"Cache-Control": "no-store"})


async def invite_redirect(request: web.Request) -> web.StreamResponse:
    bot: commands.Bot = request.app["bot"]
    url = _invite_url(bot)
    if not url:
        raise web.HTTPServiceUnavailable(text="DayZ Manager is still connecting to Discord.")
    raise web.HTTPFound(url)


# =========================================================
# SERVER
# =========================================================

async def start_web_server(bot: commands.Bot) -> web.AppRunner:
    app = web.Application()
    app["bot"] = bot

    app.router.add_get("/", homepage)
    app.router.add_get("/health", health)
    app.router.add_get("/status", status_page)
    app.router.add_get("/docs", docs_page)
    app.router.add_get("/invite", invite_redirect)
    app.router.add_get("/dashboard", dashboard_page)
    app.router.add_get("/dashboard/{guild_id}", guild_dashboard_page)
    app.router.add_get("/dashboard/{guild_id}/flags", guild_flag_tools_page)
    app.router.add_get("/dashboard/{guild_id}/tools", guild_server_tools_page)
    app.router.add_get("/dashboard/{guild_id}/status", guild_status_page)
    app.router.add_get("/auth/discord", discord_login)
    app.router.add_get("/auth/discord/callback", discord_callback)
    app.router.add_get("/auth/logout", discord_logout)

    app.router.add_get("/api/setups", setups_api)
    app.router.add_get("/api/me/setups", my_setups_api)
    app.router.add_get("/api/manage/{guild_id}/state", manage_state_api)
    app.router.add_get("/api/manage/{guild_id}/flags", manage_flags_api)
    app.router.add_post("/api/manage/{guild_id}/setup", manage_setup_api)
    app.router.add_post("/api/manage/{guild_id}/assign", manage_assign_api)
    app.router.add_post("/api/manage/{guild_id}/release", manage_release_api)
    app.router.add_post("/api/manage/{guild_id}/rename-setup", manage_rename_setup_api)
    app.router.add_post("/api/manage/{guild_id}/delete-setup", manage_delete_setup_api)
    app.router.add_get("/api/manage/{guild_id}/status", manage_status_api)
    app.router.add_post("/api/manage/{guild_id}/refresh", manage_refresh_api)
    app.router.add_get("/api/manage/{guild_id}/history", manage_history_api)
    app.router.add_get("/api/manage/{guild_id}/botstatus", manage_botstatus_api)
    app.router.add_post("/api/manage/{guild_id}/teleporter", manage_teleporter_api)
    app.router.add_get("/api/flags", flags_api)  # legacy API
    app.router.add_get("/api/flags/{guild_id}/{map_key}/{server_slug}", clean_flags_api)

    app.router.add_get("/servers", flags_directory)
    app.router.add_get("/servers/{guild_id}", server_flag_systems_page)
    app.router.add_get("/flags", flags_root_redirect)
    app.router.add_get("/flags/{guild_id}/{map_key}/{server_slug}", flag_detail_page)
    app.router.add_get("/flags-legacy", legacy_flags_page)

    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    log.info("DayZ Manager website listening | port=%d", port)
    return runner
