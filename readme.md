# Discord Statistics Bot

A Discord bot to calculate team sizes and other statistics for servers where teams are separated into roles.

The bot has two commands: `/stats`, `/stats_subscribe`. `/stats` responds with the generated statistics while `/stats_subscribe` additionally updates the message every time a member's role is changed.
To remove the dynamically updating message, a member with the admin role can react with :x: on the message.

Both commands can take arguments to modify what data is shown. The three arguments that can be added are: members, warnings, and stats with the default output being equivalent to members and warnings.

Members, shows the list of teams with member numbers and the presence of team leaders.
Warnings, shows statistics that likely require actions to be taken such as empty teams or teams missing leaders.
Stats, shows the overall statistics such as average team size.

Alternatively the statistics can be printed to console by running `discord_stats.py dump` which will immediately exit the bot after the statistics have been generated

## Required Bot Scope

When inviting the bot it requires:

- Send Messages
- Read Message History

## Future functionality
- Add ability for owner to use commands in DM channel
