# Discord Statistics Bot

A Discord bot to calculate team sizes and other statistics for servers where teams are separated into roles.

The bot currently only has one command `~stats` which responds with the generated statistics.

Alternatively the statistics can be printed to console by running `discord_stats.py dump` which will immediately exit the bot after the statistics have been generated

## Future functionality
- Filtering group's secondary teams in the warning statistics
- Adding a second command to produce a message which is automatically updated when roles are changed
    - Message can be disabled by reacting with the :x: symbol and a required role (discord.on_raw_reaction_add)
    - Use events to trigger updating the message contents (discord.on_member_update)