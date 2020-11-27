# Discord Statistics Bot

A Discord bot to calculate team sizes and other statistics for servers where teams are separated into roles.

The bot has two commands: `~stats`, `~stats_subscribe`. `~stats` responds with the generated statistics while `~stats_subscribe` additionally updates the message every time a member's role is changed.
To remove the dynamically updating message, a member with the admin role can react with :x: on the message.

Alternatively the statistics can be printed to console by running `discord_stats.py dump` which will immediately exit the bot after the statistics have been generated

## Future functionality
- Filtering group's secondary teams in the warning statistics
- Adding arguments to commands to limit and select which information is shown
