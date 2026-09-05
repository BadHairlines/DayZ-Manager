# DayZ Manager v2.4 — Full Website

DayZ Manager now runs a public website alongside the Discord bot from the same Railway service.

## Website routes

- `/` — DayZ Manager homepage
- `/flags` — public live Flag System directory with search
- `/flags/<guild>/<map>/<server>` — clean live Flag System page
- `/docs` — current bot command / feature guide
- `/status` — Discord, database, web, latency, and setup status
- `/invite` — generated Discord bot invite redirect
- `/health` — JSON health endpoint
- `/api/setups` — read-only public setup summaries
- `/api/flags/...` — read-only live flag data

The legacy `/flags?guild=...&map=...&server=...` URLs are redirected to the new clean URL format.

## Recommended Railway variables

Keep the existing `DISCORD_TOKEN` and `DATABASE_URL` variables exactly as they are. Add:

```env
DAYZ_MANAGER_BASE_URL=https://dayzmanager.xyz
```

`FLAG_WEB_BASE_URL` from v2.3 remains supported as a fallback, but `DAYZ_MANAGER_BASE_URL` takes priority.

The HTTP server listens on Railway's `PORT` environment variable (default fallback `8080`).

## Domains

Attach both domains to the same DayZ Manager Railway service:

- `dayzmanager.xyz` — main website
- `flags.dayzmanager.xyz` — optional shortcut; `/` redirects to `/flags`

Use the exact DNS records Railway provides for each custom domain.

## Discord dashboard

The `Live Website` button now generates clean URLs under `DAYZ_MANAGER_BASE_URL`, for example:

`https://dayzmanager.xyz/flags/123456789/livonia/server-1`

Flag claiming and releasing remain Administrator-only and remain inside Discord. The public website is read-only.

## Private server-owner dashboard (Discord OAuth2)

DayZ Manager includes a private `/dashboard` that signs users in with Discord and only shows Flag Systems from Discord servers they own or where Discord reports the Administrator permission.

The public `/flags` directory and individual live flag pages remain read-only and public for players. The private dashboard is a separate owner/admin view.

### Discord Developer Portal setup

In the same Discord application used by the bot:

1. Open **OAuth2** in the Discord Developer Portal.
2. Add this redirect URL exactly:
   `https://dayzmanager.xyz/auth/discord/callback`
3. Copy the application's OAuth2 **Client Secret**.
4. Never expose the client secret in GitHub or client-side website code.

### Railway variables

Add:

```env
DAYZ_MANAGER_BASE_URL=https://dayzmanager.xyz
DISCORD_CLIENT_ID=<your Discord application ID>
DISCORD_CLIENT_SECRET=<your Discord OAuth2 client secret>
DISCORD_OAUTH_REDIRECT_URI=https://dayzmanager.xyz/auth/discord/callback
```

`DISCORD_CLIENT_ID` may be omitted because DayZ Manager can fall back to the logged-in bot application's ID, but setting it explicitly is recommended.

The website requests only the Discord OAuth2 `identify` and `guilds` scopes. After login it filters the user's guild list to guilds where the user is the owner or has the Administrator permission, then intersects those guilds with active DayZ Manager Flag Systems.

The browser receives only an opaque, HTTP-only, Secure session cookie. Discord access tokens are not stored in browser cookies. Web sessions expire after 8 hours and users can sign out at `/auth/logout`.

## v2.6 Web Control Panel

The authenticated website dashboard now mirrors all current Discord commands for authorized server owners/admins:

- `/setup`
- `/setups`
- `/deletesetup`
- `/assign`
- `/release`
- `/flagstatus`
- `/flagrefresh`
- `/flaghistory`
- `/botstatus`
- `/teleporter` (only for guilds where the Discord command is enabled)

Every mutating web request is guild-scoped, requires a valid Discord OAuth administrator session, and uses a CSRF token stored server-side.


## v2.7 Website Portal Organization

The authenticated server dashboard is now split into focused sections:

- **Overview** — server summary and navigation
- **Flag System Tools** — setup, setups, assign, release, status, refresh, history, delete
- **Server Tools** — teleporter generator and future DayZ utilities
- **Bot Status** — Discord/database/latency/uptime information
- **Live Pages** — direct access to that server's public flag pages

Existing OAuth, guild scoping, CSRF protection, and management APIs remain in place.


## Website Flag System Rename

Server owners/admins can rename an existing Flag System from the private **Flag System Tools** page. The rename is atomic across `flags`, `flag_messages`, and `flag_audit_log`, preserves claims/history, rejects duplicate setup names for the same map, renames the Discord channel/category when permitted, and refreshes the Components V2 dashboard under the new setup key.


## v2.9 Deployment Hardening
- Railway healthcheck: `/health` (503 until Discord + PostgreSQL are ready).
- OAuth website sessions persist in PostgreSQL across app redeploys.
- Recommended variables: `RAILWAY_DEPLOYMENT_OVERLAP_SECONDS=15` and `RAILWAY_DEPLOYMENT_DRAINING_SECONDS=10`.


## v2.10 Vehicle Server Tool

The existing `/vehicle` Discord utility is now also available from the authenticated **Server Tools** page.

- Uses the same approved-guild restriction as the uploaded `vehicle.py` cog.
- Uses the same built-in DayZ vehicle choices.
- Generates the matching `events.xml` and `cfgeventspawns.xml` snippets.
- Supports one-click copying of either XML block from the website.
