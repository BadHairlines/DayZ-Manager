    # Small helper to resolve or create suggestions channel
    async def _get_or_create_suggestions_channel(
        self,
        guild: discord.Guild
    ) -> discord.TextChannel | None:
        # Collect any text channels whose name contains "suggest"
        candidates: list[discord.TextChannel] = [
            c for c in guild.text_channels
            if isinstance(c, discord.TextChannel)
            and "suggest" in c.name.lower()
        ]

        if candidates:
            # Prefer the "most correct" one
            def channel_score(ch: discord.TextChannel) -> tuple[int, int]:
                name = ch.name.lower()

                if name == "❔┃suggestions".lower():
                    rank = 0  # perfect match
                elif name == "suggestions":
                    rank = 1  # plain fallback
                elif "suggestions" in name:
                    rank = 2  # like "server-suggestions"
                else:
                    rank = 3  # anything with "suggest" in it

                # Second key: channel position in the guild
                return (rank, ch.position)

            best = min(candidates, key=channel_score)
            return best

        # No suitable channel found, create one
        try:
            ch = await guild.create_text_channel(
                "❔┃suggestions",
                reason="Auto-created suggestions channel for /suggest"
            )
            return ch
        except discord.Forbidden:
            return None
        except Exception as e:
            print(f"⚠️ Failed to create suggestions channel in {guild.name}: {e}")
            return None
