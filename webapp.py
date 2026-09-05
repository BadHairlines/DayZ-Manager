from __future__ import annotations

import html
import logging
import os
from urllib.parse import urlencode

from aiohttp import web
import discord
from discord.ext import commands

from cogs import utils

log = logging.getLogger("dayz-manager")


def public_base_url() -> str | None:
    explicit = os.getenv("FLAG_WEB_BASE_URL", "").strip().rstrip("/")
    if explicit:
        if not explicit.startswith(("http://", "https://")):
            explicit = f"https://{explicit}"
        return explicit

    railway = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip().rstrip("/")
    if railway:
        return f"https://{railway}"

    return None


def flag_page_url(guild_id: int | str, map_key: str, server: str) -> str | None:
    base = public_base_url()
    if not base:
        return None
    query = urlencode(
        {
            "guild": str(guild_id),
            "map": utils.normalize_map(map_key),
            "server": utils.normalize_server(server),
        }
    )
    return f"{base}/flags?{query}"


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

    available = []
    claimed = []
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
        "guild_id": guild_id,
        "guild_name": guild.name if guild else "DayZ Server",
        "guild_icon": str(guild.icon.url) if guild and guild.icon else None,
        "map": map_key,
        "map_name": map_info.get("name", map_key.title()),
        "map_image": map_info.get("image"),
        "server": server,
        "total": total,
        "available_count": len(available),
        "claimed_count": len(claimed),
        "claimed_pct": claimed_pct,
        "available": available,
        "claimed": claimed,
    }


async def health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "service": "dayz-manager-flags"})


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


async def flags_page(request: web.Request) -> web.Response:
    bot: commands.Bot = request.app["bot"]
    guild_id = request.query.get("guild", "").strip()
    map_key = request.query.get("map", "").strip()
    server = request.query.get("server", "").strip()

    if not guild_id or not map_key or not server:
        return web.Response(text=_error_page("Missing flag setup information."), content_type="text/html", status=400)

    payload = await _get_payload(bot, guild_id, map_key, server)
    if not payload:
        return web.Response(text=_error_page("This flag setup could not be found."), content_type="text/html", status=404)

    title = html.escape(f"{payload['guild_name']} • {payload['map_name']} • {payload['server']}")
    guild_name = html.escape(payload["guild_name"])
    map_name = html.escape(payload["map_name"])
    server_name = html.escape(payload["server"])
    guild_icon = html.escape(payload["guild_icon"] or "")
    map_image = html.escape(payload["map_image"] or "")
    query = html.escape(urlencode({"guild": guild_id, "map": map_key, "server": server}), quote=True)

    page = f"""<!doctype html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<meta name=\"theme-color\" content=\"#0b0f14\">
<title>{title} | DayZ Manager</title>
<style>
:root{{--bg:#080b10;--panel:#10161f;--panel2:#151d28;--line:#263241;--text:#f4f7fb;--muted:#93a4b8;--green:#43e18c;--red:#ff6577;--blue:#59a7ff;--gold:#f4c95d;}}
*{{box-sizing:border-box}} body{{margin:0;background:radial-gradient(circle at 15% 0%,#162231 0,#0a0e14 35%,#06090d 100%);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;min-height:100vh}}
.wrap{{max-width:1180px;margin:auto;padding:30px 18px 60px}} .top{{display:flex;align-items:center;gap:16px;margin-bottom:22px}} .logo{{width:62px;height:62px;border-radius:18px;background:#141c26;border:1px solid var(--line);display:grid;place-items:center;font-size:30px;overflow:hidden;box-shadow:0 12px 30px #0006}} .logo img{{width:100%;height:100%;object-fit:cover}}
h1{{font-size:clamp(28px,5vw,48px);margin:0;letter-spacing:-1.4px}} .sub{{color:var(--muted);font-size:15px;margin-top:5px}} .hero{{position:relative;overflow:hidden;background:linear-gradient(135deg,#111924ee,#0e151eee);border:1px solid var(--line);border-radius:24px;padding:24px;box-shadow:0 20px 60px #0007}} .hero:before{{content:\"\";position:absolute;inset:0;background:linear-gradient(90deg,#0f1823 20%,transparent 75%);z-index:0}} .hero-bg{{position:absolute;inset:0 0 0 42%;opacity:.16;background-size:cover;background-position:center;filter:saturate(.8)}} .hero>*{{position:relative;z-index:1}}
.badge{{display:inline-flex;gap:8px;align-items:center;border:1px solid #2b3c4e;background:#111923cc;color:#b8c8d8;border-radius:999px;padding:7px 11px;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.08em}} .live-dot{{width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 15px var(--green)}}
.hero-title{{font-size:clamp(24px,4vw,38px);font-weight:850;margin:16px 0 4px}} .stats{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:22px}} .stat{{background:#0b1119cc;border:1px solid var(--line);border-radius:17px;padding:16px}} .stat .n{{font-size:28px;font-weight:850}} .stat .l{{color:var(--muted);font-size:13px;margin-top:4px}} .green{{color:var(--green)}} .red{{color:var(--red)}} .gold{{color:var(--gold)}}
.progress{{height:8px;border-radius:99px;background:#202a36;margin-top:17px;overflow:hidden}} .progress span{{display:block;height:100%;background:linear-gradient(90deg,var(--green),var(--gold),var(--red));transition:width .35s ease}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:18px}} .card{{background:linear-gradient(180deg,#111821,#0d131a);border:1px solid var(--line);border-radius:22px;overflow:hidden;box-shadow:0 15px 35px #0004}} .card-head{{padding:18px 20px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center}} .card-title{{font-size:18px;font-weight:800}} .count{{color:var(--muted);font-size:13px;border:1px solid var(--line);background:#0b1017;padding:5px 9px;border-radius:99px}}
.list{{padding:10px}} .item{{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px 12px;border-radius:13px}} .item:hover{{background:#18212c}} .flag{{font-weight:750}} .owner{{color:#b8c5d4;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:55%}} .status{{width:9px;height:9px;border-radius:50%;flex:0 0 auto;margin-right:9px}} .left{{display:flex;align-items:center;min-width:0}} .empty{{padding:28px 18px;text-align:center;color:var(--muted)}}
.footer{{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;color:#718398;font-size:12px;margin:20px 4px 0}} .updated{{display:flex;gap:7px;align-items:center}} @media(max-width:760px){{.grid{{grid-template-columns:1fr}}.stats{{grid-template-columns:1fr 1fr 1fr}}.hero{{padding:19px}}.owner{{max-width:46%}}}} @media(max-width:480px){{.stats{{gap:7px}}.stat{{padding:12px 9px}}.stat .n{{font-size:22px}}.top{{align-items:flex-start}}}}
</style>
</head>
<body>
<div class=\"wrap\">
  <div class=\"top\"><div class=\"logo\" id=\"guildLogo\">🚩</div><div><h1>DayZ Manager</h1><div class=\"sub\">Live Flag System Portal</div></div></div>
  <section class=\"hero\"><div class=\"hero-bg\" id=\"heroBg\"></div><span class=\"badge\"><span class=\"live-dot\"></span> Live from DayZ Manager</span><div class=\"hero-title\" id=\"guildName\">{guild_name}</div><div class=\"sub\"><span id=\"mapName\">{map_name}</span> • <span id=\"serverName\">{server_name}</span></div><div class=\"stats\"><div class=\"stat\"><div class=\"n green\" id=\"availableCount\">—</div><div class=\"l\">Available</div></div><div class=\"stat\"><div class=\"n red\" id=\"claimedCount\">—</div><div class=\"l\">Claimed</div></div><div class=\"stat\"><div class=\"n gold\" id=\"totalCount\">—</div><div class=\"l\">Total Flags</div></div></div><div class=\"progress\"><span id=\"progressBar\" style=\"width:0%\"></span></div></section>
  <div class=\"grid\"><section class=\"card\"><div class=\"card-head\"><div class=\"card-title green\">🟢 Available Flags</div><div class=\"count\" id=\"availableBadge\">0</div></div><div class=\"list\" id=\"availableList\"></div></section><section class=\"card\"><div class=\"card-head\"><div class=\"card-title red\">🔴 Claimed Flags</div><div class=\"count\" id=\"claimedBadge\">0</div></div><div class=\"list\" id=\"claimedList\"></div></section></div>
  <div class=\"footer\"><span>Powered by DayZ Manager</span><span class=\"updated\">● <span id=\"updatedAt\">Connecting…</span></span></div>
</div>
<script>
const api = '/api/flags?{query}';
const esc = s => String(s ?? '').replace(/[&<>\"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}}[c]));
function render(data) {{
 document.getElementById('guildName').textContent=data.guild_name; document.getElementById('mapName').textContent=data.map_name; document.getElementById('serverName').textContent=data.server;
 document.getElementById('availableCount').textContent=data.available_count; document.getElementById('claimedCount').textContent=data.claimed_count; document.getElementById('totalCount').textContent=data.total; document.getElementById('availableBadge').textContent=data.available_count; document.getElementById('claimedBadge').textContent=data.claimed_count; document.getElementById('progressBar').style.width=data.claimed_pct+'%';
 const logo=document.getElementById('guildLogo'); if(data.guild_icon) logo.innerHTML='<img alt="Server icon" src="'+esc(data.guild_icon)+'">';
 const bg=document.getElementById('heroBg'); if(data.map_image) bg.style.backgroundImage='url("'+String(data.map_image).replace(/\"/g,'')+'")';
 document.getElementById('availableList').innerHTML=data.available.length?data.available.map(x=>'<div class="item"><div class="left"><span class="status" style="background:var(--green)"></span><span class="flag">'+esc(x.flag)+'</span></div><span class="owner green">AVAILABLE</span></div>').join(''):'<div class="empty">No flags are currently available.</div>';
 document.getElementById('claimedList').innerHTML=data.claimed.length?data.claimed.map(x=>'<div class="item"><div class="left"><span class="status" style="background:var(--red)"></span><span class="flag">'+esc(x.flag)+'</span></div><span class="owner">'+esc(x.role_name)+'</span></div>').join(''):'<div class="empty">No flags are currently claimed.</div>';
 document.getElementById('updatedAt').textContent='Updated '+new Date().toLocaleTimeString();
}}
async function refresh() {{ try {{ const r=await fetch(api,{{cache:'no-store'}}); if(!r.ok) throw new Error(); render(await r.json()); }} catch(e) {{ document.getElementById('updatedAt').textContent='Connection interrupted — retrying'; }} }}
refresh(); setInterval(refresh, 10000);
</script>
</body></html>"""
    return web.Response(text=page, content_type="text/html", headers={"Cache-Control": "no-store"})


def _error_page(message: str) -> str:
    return f"""<!doctype html><html><head><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>DayZ Manager</title><style>body{{margin:0;background:#080b10;color:#fff;font-family:system-ui;display:grid;place-items:center;min-height:100vh}}div{{text-align:center;background:#111821;border:1px solid #263241;border-radius:20px;padding:32px;max-width:520px;margin:20px}}p{{color:#93a4b8}}</style></head><body><div><h1>🚩 DayZ Manager</h1><p>{html.escape(message)}</p></div></body></html>"""


async def start_web_server(bot: commands.Bot) -> web.AppRunner:
    app = web.Application()
    app["bot"] = bot
    app.router.add_get("/health", health)
    app.router.add_get("/api/flags", flags_api)
    app.router.add_get("/flags", flags_page)

    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    log.info("Flag web portal listening | port=%d", port)
    return runner
