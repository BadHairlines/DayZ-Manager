import os, asyncio, importlib, discord
from discord.ext import commands
from cogs import utils
intents=discord.Intents.default();intents.guilds=True;intents.members=True;intents.guild_messages=True;intents.message_content=True;intents.guild_reactions=True
bot=commands.Bot(command_prefix="!",intents=intents);bot.synced=False
def resolve_flag_manage_view():
    for path,cls in(("cogs.ui_views","FlagManageView"),("cogs.assign","FlagManageView")):
        try:
            mod=importlib.import_module(path);view_cls=getattr(mod,cls,None)
            if view_cls:return view_cls
        except Exception:pass
    return None
async def register_persistent_views():
    FlagManageView=resolve_flag_manage_view()
    if FlagManageView is None or utils.db_pool is None:return
    async with utils.db_pool.acquire() as conn:
        try:rows=await conn.fetch("SELECT guild_id,map,message_id FROM flag_messages;")
        except Exception:return
    for row in rows:
        guild=bot.get_guild(int(row["guild_id"]))
        if not guild:continue
        try:view=FlagManageView(guild,row["map"],"N/A",bot);bot.add_view(view,message_id=int(row["message_id"]))
        except Exception:pass
SKIP_FILES={"__init__.py","utils.py","faction_utils.py","ui_views.py"}
async def load_cogs():
    for root,dirs,files in os.walk("cogs"):
        dirs[:]=[d for d in dirs if d not in("__pycache__","helpers")]
        for filename in files:
            if not filename.endswith(".py"):continue
            if filename in SKIP_FILES or filename.startswith("_"):continue
            module_path=os.path.join(root,filename).replace(os.sep,".")[:-3]
            try:await bot.load_extension(module_path)
            except Exception:pass
@bot.event
async def on_ready():
    if not bot.synced:
        try:await bot.tree.sync();bot.synced=True
        except Exception:pass
    await register_persistent_views()
@bot.command(name="sync",help="Owner: force re-sync slash commands.")
@commands.is_owner()
async def _sync(ctx:commands.Context):
    cmds=await bot.tree.sync();await ctx.send(f"Slash commands synced: {len(cmds)}")
async def main():
    await asyncio.sleep(1);await utils.init_db();await load_cogs()
    try:from cogs.ui_views import FlagManageView;bot.add_view(FlagManageView())
    except Exception:pass
    token=os.getenv("DISCORD_TOKEN")
    if not token:raise RuntimeError("DISCORD_TOKEN not set in environment.")
    async with bot:
        for attempt in range(3):
            try:await bot.start(token);break
            except discord.HTTPException as e:
                if e.status==429:
                    backoff=30*(attempt+1);await asyncio.sleep(backoff)
                else:raise
if __name__=="__main__":
    try:asyncio.run(main())
    except KeyboardInterrupt:pass
