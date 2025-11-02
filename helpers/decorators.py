from discord import app_commands

def admin_only():
    """Decorator for admin-only slash commands."""
    async def predicate(interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You must be an administrator to use this command.",
                ephemeral=True
            )
            return False
        return True
    return app_commands.check(predicate)


MAP_CHOICES = [
    app_commands.Choice(name="Livonia", value="livonia"),
    app_commands.Choice(name="Chernarus", value="chernarus"),
    app_commands.Choice(name="Sakhal", value="sakhal"),
]
