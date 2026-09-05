from __future__ import annotations

import html
import json
import logging
import os
import re
import secrets
import time
from urllib.parse import quote, urlencode

import aiohttp

from aiohttp import web
import discord
from discord.ext import commands

from cogs import utils

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
        item = {"flag": str(row["flag"])}
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
    sessions = await utils.get_flag_sessions(guild_id)
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
:root{--bg:#090d12;--panel:#111821;--panel2:#0d141c;--line:#283545;--text:#f5f7fb;--muted:#92a5bb;--blue:#57a8ff;--green:#43e99c;--red:#ff5775;--gold:#f2d85e;--shadow:0 22px 70px #0008}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:radial-gradient(circle at 20% -10%,#1a2839 0,transparent 38%),radial-gradient(circle at 90% 10%,#171f2b 0,transparent 30%),var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;min-height:100vh}a{color:inherit;text-decoration:none}.wrap{width:min(1180px,calc(100% - 34px));margin:auto}.nav{height:78px;display:flex;align-items:center;justify-content:space-between;gap:20px}.brand{display:flex;align-items:center;gap:12px;font-weight:900;font-size:20px}.brandmark{width:39px;height:39px;border:1px solid var(--line);background:linear-gradient(145deg,#1e2a39,#111821);border-radius:12px;display:grid;place-items:center;box-shadow:0 10px 30px #0005}.navlinks{display:flex;gap:7px;align-items:center;flex-wrap:wrap}.navlinks a{padding:9px 12px;border-radius:10px;color:#b9c7d6;font-size:14px}.navlinks a:hover{background:#16202b;color:#fff}.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:12px 16px;border-radius:12px;border:1px solid var(--line);background:#151f2a;font-weight:750;transition:.18s transform,.18s border-color,.18s background}.btn:hover{transform:translateY(-1px);border-color:#49617b;background:#1a2735}.btn.primary{background:linear-gradient(135deg,#4b9cff,#7667ff);border-color:transparent;color:#fff;box-shadow:0 12px 35px #4d75ff33}.hero-home{padding:72px 0 55px;display:grid;grid-template-columns:1.15fr .85fr;gap:45px;align-items:center}.eyebrow{display:inline-flex;gap:9px;align-items:center;color:#afc3d8;border:1px solid var(--line);border-radius:999px;padding:7px 11px;background:#111923aa;font-size:12px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.dot{width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 14px var(--green)}h1{font-size:clamp(42px,7vw,78px);line-height:.98;letter-spacing:-3px;margin:18px 0 20px}.gradient{background:linear-gradient(100deg,#fff 5%,#82bfff 48%,#9d8cff 88%);-webkit-background-clip:text;background-clip:text;color:transparent}.lead{font-size:18px;line-height:1.7;color:#a7b7c9;max-width:720px}.hero-actions{display:flex;gap:11px;flex-wrap:wrap;margin-top:28px}.mock{background:linear-gradient(145deg,#121b25,#0c1118);border:1px solid var(--line);border-radius:25px;padding:19px;box-shadow:var(--shadow);transform:rotate(1.1deg)}.mock-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}.mini-stat-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.mini-stat{background:#0b1118;border:1px solid #233041;border-radius:14px;padding:13px}.mini-stat strong{display:block;font-size:22px}.mini-list{margin-top:10px;border:1px solid #243141;border-radius:14px;overflow:hidden}.mini-row{padding:11px 13px;border-bottom:1px solid #1f2b39;display:flex;justify-content:space-between;font-size:13px}.mini-row:last-child{border:0}.section{padding:58px 0}.section-title{font-size:clamp(29px,4vw,42px);letter-spacing:-1.5px;margin:0 0 10px}.section-sub{color:var(--muted);max-width:740px;line-height:1.6}.feature-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:28px}.feature{background:linear-gradient(180deg,#111923,#0d131a);border:1px solid var(--line);border-radius:18px;padding:22px}.feature .icon{font-size:26px}.feature h3{margin:14px 0 7px}.feature p{color:var(--muted);line-height:1.55;font-size:14px;margin:0}.stat-band{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:25px}.big-stat{border:1px solid var(--line);background:#101720;border-radius:17px;padding:20px}.big-stat strong{font-size:30px;display:block}.big-stat span{color:var(--muted);font-size:13px}.card{background:linear-gradient(180deg,#111821,#0d131a);border:1px solid var(--line);border-radius:20px;box-shadow:0 15px 40px #0004}.directory-tools{display:flex;gap:10px;margin:22px 0}.search{width:100%;padding:14px 16px;border-radius:13px;border:1px solid var(--line);background:#0c1219;color:#fff;outline:none;font-size:15px}.search:focus{border-color:#567596}.server-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.server-card{padding:19px;display:flex;gap:15px;align-items:flex-start}.server-icon{width:48px;height:48px;border-radius:14px;background:#182331;border:1px solid var(--line);display:grid;place-items:center;overflow:hidden;flex:0 0 auto}.server-icon img{width:100%;height:100%;object-fit:cover}.server-main{min-width:0;flex:1}.server-name{font-size:17px;font-weight:850;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.meta{color:var(--muted);font-size:13px;margin-top:4px}.counts{display:flex;gap:10px;flex-wrap:wrap;margin-top:13px;font-size:12px}.pill{border:1px solid var(--line);border-radius:999px;padding:5px 9px;background:#0b1118}.green{color:var(--green)}.red{color:var(--red)}.gold{color:var(--gold)}.flag-hero{position:relative;overflow:hidden;padding:24px}.flag-hero-bg{position:absolute;inset:0 0 0 48%;opacity:.13;background-size:cover;background-position:center}.flag-hero>*{position:relative;z-index:1}.flag-head{display:flex;align-items:center;gap:14px}.flag-logo{width:58px;height:58px;border-radius:16px;background:#172231;border:1px solid var(--line);display:grid;place-items:center;overflow:hidden;font-size:28px}.flag-logo img{width:100%;height:100%;object-fit:cover}.flag-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:21px}.flag-stat{border:1px solid var(--line);background:#0a1118cc;border-radius:15px;padding:15px}.flag-stat strong{font-size:26px}.progress{height:7px;background:#263240;border-radius:999px;overflow:hidden;margin-top:15px}.progress span{height:100%;display:block;background:linear-gradient(90deg,var(--green),var(--gold),var(--red))}.flag-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}.list-head{padding:17px 18px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between}.list{padding:8px}.flag-row{padding:11px 10px;border-radius:11px;display:flex;justify-content:space-between;gap:12px}.flag-row:hover{background:#17212c}.owner{color:#b0c0d0;max-width:55%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.empty{padding:28px;color:var(--muted);text-align:center}.docs{display:grid;grid-template-columns:240px 1fr;gap:20px;align-items:start}.toc{position:sticky;top:18px;padding:15px}.toc a{display:block;padding:9px 10px;color:#a8b9cb;border-radius:9px;font-size:14px}.toc a:hover{background:#17212c;color:#fff}.doc-body{padding:26px}.doc-body h2{margin-top:34px}.command{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:#c7dbef;background:#091019;border:1px solid #243244;padding:3px 7px;border-radius:7px}.status-box{padding:23px}.status-line{display:flex;justify-content:space-between;gap:15px;padding:12px 0;border-bottom:1px solid #202c39}.status-line:last-child{border:0}.footer{border-top:1px solid #1e2936;margin-top:60px;padding:28px 0 40px;color:#72859a;font-size:13px;display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}.user-card{display:flex;align-items:center;gap:12px}.user-avatar{width:44px;height:44px;border-radius:50%;border:1px solid var(--line);object-fit:cover}.dashboard-head{display:flex;justify-content:space-between;gap:20px;align-items:center;flex-wrap:wrap}.notice{padding:16px 18px;border:1px solid var(--line);background:#101822;border-radius:14px;color:#b8c7d8}.private-badge{display:inline-flex;align-items:center;gap:7px;color:#b9c9db;font-size:12px;font-weight:800;border:1px solid var(--line);padding:6px 10px;border-radius:999px;background:#0b121a}.hidden{display:none!important}@media(max-width:900px){.hero-home{grid-template-columns:1fr;padding-top:45px}.mock{transform:none}.feature-grid{grid-template-columns:1fr 1fr}.stat-band{grid-template-columns:1fr 1fr}.server-grid{grid-template-columns:1fr}.docs{grid-template-columns:1fr}.toc{position:static}.flag-grid{grid-template-columns:1fr}}@media(max-width:620px){.nav{height:auto;padding:14px 0;align-items:flex-start}.navlinks a:not(.keep){display:none}.hero-home{padding-top:34px}.feature-grid{grid-template-columns:1fr}.flag-stats{grid-template-columns:1fr 1fr 1fr}.flag-stat{padding:11px}.flag-stat strong{font-size:21px}.wrap{width:min(100% - 22px,1180px)}h1{letter-spacing:-2px}.stat-band{grid-template-columns:1fr 1fr}}
"""


def _nav(invite_url: str | None = None) -> str:
    invite = f'<a class="btn primary keep" href="{html.escape(invite_url)}">Add to Discord</a>' if invite_url else ""
    return f"""
<nav class="nav wrap">
  <a class="brand" href="/"><span class="brandmark">🚩</span><span>DayZ Manager</span></a>
  <div class="navlinks">
    <a href="/flags">Live Flags</a>
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
      <div class="hero-actions"><a class="btn primary" href="/dashboard">🔐 My Dashboard</a><a class="btn" href="/invite">➕ Add DayZ Manager</a><a class="btn" href="/flags">🚩 Browse Live Flags</a><a class="btn" href="/docs">📖 View Commands</a></div>
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
      <div class="feature"><div class="icon">🔐</div><h3>Administrator Controlled</h3><p>Claim and release actions stay administrator-only. Faction roles identify owners; they never grant management permission.</p></div>
      <div class="feature"><div class="icon">🕘</div><h3>Audit History</h3><p>See which flag changed, which faction owned it, who performed the action, and when it happened.</p></div>
      <div class="feature"><div class="icon">🗺️</div><h3>Map Ready</h3><p>Support for Chernarus, Livonia, Sakhal, and Nasdara is built into the Flag System.</p></div>
      <div class="feature"><div class="icon">⚙️</div><h3>Self-Service Setups</h3><p>Server administrators can view, refresh, inspect, and delete their own server's Flag System setups.</p></div>
      <div class="feature"><div class="icon">🌐</div><h3>Public Live Pages</h3><p>Give players a clean link to check flag availability without needing to dig through Discord interactions.</p></div>
    </div>
  </section>
  <section class="section"><div class="card" style="padding:30px;text-align:center"><h2 class="section-title">Ready to see it live?</h2><p class="section-sub" style="margin:0 auto 22px">Browse DayZ communities using DayZ Manager, then open that server to view its live Flag Systems.</p><a class="btn primary" href="/flags">Browse Servers Using DayZ Manager →</a></div></section>
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
<main class="wrap"><section class="section" style="padding-top:60px"><div class="card" style="padding:34px;max-width:720px;margin:auto;text-align:center"><span class="private-badge">🔐 PRIVATE SERVER-OWNER AREA</span><h1 style="font-size:clamp(36px,6vw,58px)">Your DayZ Manager <span class="gradient">Dashboard</span></h1><p class="lead" style="margin:0 auto 24px">Sign in with Discord. DayZ Manager will only show Flag Systems from servers you own or where you have Administrator permission.</p><a class="btn primary" href="/auth/discord">Login with Discord</a><p class="meta" style="margin-top:18px">Requested scopes: identify + guilds. Claim and release actions remain inside Discord.</p></div></section></main>"""
        return web.Response(
            text=_page("My Dashboard — DayZ Manager", body, _invite_url(bot)),
            content_type="text/html",
            headers={"Cache-Control": "no-store"},
        )

    allowed = set(session.get("guild_ids", []))
    setups = [item for item in await _public_setups(bot) if item["guild_id"] in allowed]
    user = session.get("user", {})
    avatar = user.get("avatar_url")
    avatar_html = (
        f'<img class="user-avatar" src="{html.escape(avatar)}" alt="">'
        if avatar
        else '<span class="user-avatar" style="display:grid;place-items:center;background:#172231">👤</span>'
    )

    cards = []
    for item in setups:
        icon = (
            f'<img alt="" src="{html.escape(item["guild_icon"])}">'
            if item["guild_icon"]
            else "🚩"
        )
        url = item["url"] or "#"
        cards.append(
            f'<a class="card server-card" href="{html.escape(url)}">'
            f'<div class="server-icon">{icon}</div><div class="server-main">'
            f'<div class="server-name">{html.escape(item["guild_name"])}</div>'
            f'<div class="meta">{html.escape(item["map_name"])} • {html.escape(item["server"])}</div>'
            f'<div class="counts"><span class="pill green">🟢 {item["available_count"]} Available</span>'
            f'<span class="pill red">🔴 {item["claimed_count"]} Claimed</span>'
            f'<span class="pill">🏴 {item["total"]} Total</span></div></div>'
            '<span style="color:#7f93a9">→</span></a>'
        )

    entries = "".join(cards) if cards else (
        '<div class="card empty" style="grid-column:1/-1"><h3>No Flag Systems found</h3>'
        '<p>DayZ Manager is not currently tracking a Flag System in any Discord server you own/administer.</p>'
        '<a class="btn" href="/invite">Add DayZ Manager</a></div>'
    )
    username = html.escape(str(user.get("username", "Discord User")))
    body = f"""
<main class="wrap"><section class="section" style="padding-top:45px"><div class="dashboard-head"><div><span class="private-badge">🔐 PRIVATE DASHBOARD</span><h1 style="font-size:clamp(38px,6vw,64px);margin-bottom:10px">My <span class="gradient">Flag Systems</span></h1><p class="section-sub">Only setups from Discord servers you own or administer are shown here.</p></div><div class="user-card">{avatar_html}<div><strong>{username}</strong><div class="meta">{len(allowed)} admin server(s) authorized</div><a class="meta" href="/auth/logout">Sign out</a></div></div></div><div class="notice" style="margin:20px 0">🛡️ Server access is verified from your Discord OAuth permissions at login. Knowing or changing a guild ID in a URL does not grant private dashboard access.</div><div class="server-grid">{entries}</div></section></main>"""
    return web.Response(
        text=_page("My Flag Systems — DayZ Manager", body, _invite_url(bot)),
        content_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


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


async def flags_directory(request: web.Request) -> web.Response:
    bot: commands.Bot = request.app["bot"]

    # Backward compatibility for v2.3 links that used /flags?guild=...&map=...&server=...
    legacy_guild = request.query.get("guild", "").strip()
    legacy_map = request.query.get("map", "").strip()
    legacy_server = request.query.get("server", "").strip()
    if legacy_guild and legacy_map and legacy_server:
        clean = flag_page_url(legacy_guild, legacy_map, legacy_server)
        if clean:
            clean_path = clean.split("/flags/", 1)[-1]
            raise web.HTTPFound(f"/flags/{clean_path}")

    # Public /flags is a directory of Discord servers using DayZ Manager.
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
                '<main class="wrap"><section class="section"><div class="card empty"><h2>🚩 Server not found</h2><p>This server has no public Flag Systems or DayZ Manager is no longer connected to it.</p><a class="btn" href="/flags">← Servers Using DayZ Manager</a></div></section></main>',
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
<a href="/flags" class="meta">← Servers Using DayZ Manager</a>
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
        return web.Response(text=_page("Flag System Not Found", '<main class="wrap"><section class="section"><div class="card empty"><h2>🚩 Flag System not found</h2><p>This setup may have been removed or the link is invalid.</p><a class="btn" href="/flags">Browse live Flag Systems</a></div></section></main>', _invite_url(bot)), content_type="text/html", status=404)
    payload = await _get_payload(bot, guild_id, map_key, server)
    if not payload:
        return web.Response(text=_page("Flag System Not Found", '<main class="wrap"><section class="section"><div class="card empty"><h2>🚩 Flag System not found</h2></div></section></main>', _invite_url(bot)), content_type="text/html", status=404)

    map_bg = html.escape(payload.get("map_image") or "")
    guild_icon = f'<img alt="Server icon" src="{html.escape(payload["guild_icon"])}">' if payload.get("guild_icon") else "🚩"
    api_path = f"/api/flags/{quote(guild_id, safe='')}/{quote(utils.normalize_map(map_key), safe='')}/{quote(_slug(server), safe='')}"
    initial_json = json.dumps(payload).replace("<", "\\u003c")
    body = f"""
<main class="wrap"><section class="section" style="padding-top:36px"><a href="/servers/{quote(guild_id, safe='')}" class="meta">← Server Flag Systems</a><section class="card flag-hero" style="margin-top:15px"><div class="flag-hero-bg" id="heroBg" style="background-image:url('{map_bg}')"></div><div class="flag-head"><div class="flag-logo" id="guildLogo">{guild_icon}</div><div><span class="eyebrow"><span class="dot"></span> Live from DayZ Manager</span><h2 id="guildName" style="font-size:clamp(25px,4vw,38px);margin:9px 0 3px">{html.escape(payload['guild_name'])}</h2><div class="meta"><span id="mapName">{html.escape(payload['map_name'])}</span> • <span id="serverName">{html.escape(payload['server'])}</span></div></div></div><div class="flag-stats"><div class="flag-stat"><strong class="green" id="availableCount">{payload['available_count']}</strong><div class="meta">Available</div></div><div class="flag-stat"><strong class="red" id="claimedCount">{payload['claimed_count']}</strong><div class="meta">Claimed</div></div><div class="flag-stat"><strong class="gold" id="totalCount">{payload['total']}</strong><div class="meta">Total Flags</div></div></div><div class="progress"><span id="progressBar" style="width:{payload['claimed_pct']}%"></span></div></section><div class="flag-grid"><section class="card"><div class="list-head"><strong class="green">🟢 Available Flags</strong><span class="pill" id="availableBadge">{payload['available_count']}</span></div><div class="list" id="availableList"></div></section><section class="card"><div class="list-head"><strong class="red">🔴 Claimed Flags</strong><span class="pill" id="claimedBadge">{payload['claimed_count']}</span></div><div class="list" id="claimedList"></div></section></div><div class="meta" style="display:flex;justify-content:space-between;gap:15px;margin:14px 3px"><span>Read-only public view • Management stays in Discord</span><span id="updatedAt">Connecting…</span></div></section></main>
<script>const API={json.dumps(api_path)};const INITIAL={initial_json};const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));function render(d){{document.getElementById('guildName').textContent=d.guild_name;document.getElementById('mapName').textContent=d.map_name;document.getElementById('serverName').textContent=d.server;document.getElementById('availableCount').textContent=d.available_count;document.getElementById('claimedCount').textContent=d.claimed_count;document.getElementById('totalCount').textContent=d.total;document.getElementById('availableBadge').textContent=d.available_count;document.getElementById('claimedBadge').textContent=d.claimed_count;document.getElementById('progressBar').style.width=d.claimed_pct+'%';document.getElementById('availableList').innerHTML=d.available.length?d.available.map(x=>'<div class="flag-row"><span>🟢 <strong>'+esc(x.flag)+'</strong></span><span class="green">AVAILABLE</span></div>').join(''):'<div class="empty">No flags are currently available.</div>';document.getElementById('claimedList').innerHTML=d.claimed.length?d.claimed.map(x=>'<div class="flag-row"><span>🔴 <strong>'+esc(x.flag)+'</strong></span><span class="owner">'+esc(x.role_name)+'</span></div>').join(''):'<div class="empty">No flags are currently claimed.</div>';document.getElementById('updatedAt').textContent='Updated '+new Date().toLocaleTimeString()}}async function refresh(){{try{{const r=await fetch(API,{{cache:'no-store'}});if(!r.ok)throw new Error('HTTP '+r.status);render(await r.json())}}catch(e){{document.getElementById('updatedAt').textContent='Connection interrupted — retrying'}}}}render(INITIAL);setInterval(refresh,10000);</script>"""
    return web.Response(text=_page(f"{payload['guild_name']} — Live Flags", body, _invite_url(bot), f"Live available and claimed flags for {payload['guild_name']} — {payload['map_name']} {payload['server']}."), content_type="text/html", headers={"Cache-Control": "no-store"})


async def docs_page(request: web.Request) -> web.Response:
    bot: commands.Bot = request.app["bot"]
    body = """
<main class="wrap"><section class="section" style="padding-top:45px"><span class="eyebrow">📖 Documentation</span><h1 style="font-size:clamp(38px,6vw,64px)">DayZ Manager <span class="gradient">commands</span></h1><p class="lead">A quick guide for server owners and administrators using the current Flag System and utilities.</p><div class="docs"><aside class="card toc"><a href="#setup">Setup</a><a href="#flags">Flag Management</a><a href="#admin">Admin Tools</a><a href="#web">Live Website</a><a href="#utility">Utilities</a></aside><article class="card doc-body"><h2 id="setup">Flag System Setup</h2><p><span class="command">/setup</span> creates/configures a Flag System for a selected map and server.</p><p><span class="command">/setups</span> lists Flag System setups belonging to the current Discord server.</p><p><span class="command">/deletesetup</span> permanently removes one of the current Discord server's setups after confirmation.</p><h2 id="flags">Flag Management</h2><p><span class="command">/assign</span> assigns an available flag to a faction role. Administrator-only.</p><p><span class="command">/release</span> releases a claimed flag. Administrator-only.</p><p>The permanent Components V2 dashboard also provides Claim, Release, View Flags, Find Flag, History, Admin Panel, and Live Website controls.</p><h2 id="admin">Admin Tools</h2><p><span class="command">/flagstatus</span> checks a setup's health.</p><p><span class="command">/flagrefresh</span> manually refreshes or repairs a setup dashboard.</p><p><span class="command">/flaghistory</span> shows recent flag audit history.</p><p><span class="command">/botstatus</span> shows bot/database status and latency.</p><h2 id="web">Live Website</h2><p>Every active Flag System has a public read-only page showing available and claimed flags. Server owners and administrators can also use <span class="command">/dashboard</span> on the website to sign in with Discord and see only Flag Systems from servers they own/administer. Claim/release management remains inside Discord.</p><h2 id="utility">Utilities</h2><p><span class="command">/teleporter</span> generates DayZ teleporter configuration files.</p></article></div></section></main>"""
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
    app.router.add_get("/auth/discord", discord_login)
    app.router.add_get("/auth/discord/callback", discord_callback)
    app.router.add_get("/auth/logout", discord_logout)

    app.router.add_get("/api/setups", setups_api)
    app.router.add_get("/api/me/setups", my_setups_api)
    app.router.add_get("/api/flags", flags_api)  # legacy API
    app.router.add_get("/api/flags/{guild_id}/{map_key}/{server_slug}", clean_flags_api)

    app.router.add_get("/flags", flags_directory)
    app.router.add_get("/servers/{guild_id}", server_flag_systems_page)
    app.router.add_get("/flags/{guild_id}/{map_key}/{server_slug}", flag_detail_page)
    app.router.add_get("/flags-legacy", legacy_flags_page)

    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    log.info("DayZ Manager website listening | port=%d", port)
    return runner
