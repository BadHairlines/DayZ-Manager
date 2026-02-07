@app_commands.command(
    name="guilds",
    description="List all servers the bot is in (owner only)."
)
async def guilds(self, interaction: discord.Interaction):
    # Check if the user is the bot owner
    app_info = await self.bot.application_info()
    if interaction.user.id != app_info.owner.id:
        return await interaction.response.send_message(
            "🚫 Only the bot owner can use this command.", ephemeral=True
        )

    if not self.bot.guilds:
        return await interaction.response.send_message(
            "I'm not in any servers!", ephemeral=True
        )

    lines = []
    for g in self.bot.guilds:
        owner = g.owner  # May be None if not cached
        if not owner:
            owner = await self.bot.fetch_user(g.owner_id)
        lines.append(f"{g.name} ({g.id}) — Owner: {owner} ({owner.id}) — {g.member_count} members")

    # Split messages into chunks under 2000 characters
    chunk_size = 2000
    message = ""
    await interaction.response.defer(ephemeral=True)
    for line in lines:
        if len(message) + len(line) + 1 > chunk_size:
            await interaction.followup.send(f"```{message}```", ephemeral=True)
            message = ""
        message += line + "\n"
    if message:
        await interaction.followup.send(f"```{message}```", ephemeral=True)
