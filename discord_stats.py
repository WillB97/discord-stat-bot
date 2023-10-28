#!/usr/bin/env python3
"""A bot to generate statistics for the discord server."""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from statistics import mean
from typing import Any, Dict, List, NamedTuple, Optional, Tuple, Union

import discord
import discord.utils
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# name of key roles for the server
ADMIN_ROLE = 'Blueshirt'  # admins can use the bot
LEADER_ROLE = 'Team Supervisor'  # leaders are excluded from the team member count
TEAM_PREFIX = 'team-'  # prefix of role names for teams

# file to store messages being dynamically updated between reboots
SUBSCRIBE_MSG_FILE = 'subscribed_messages.json'
SUBSCRIBED_MESSAGES: List['SubscribedMessage'] = []


class SubscribedMessage(NamedTuple):
    """A message that is updated when the server statistics change."""

    channel_id: int
    message_id: int
    members: bool = True
    warnings: bool = True
    stats: bool = False

    @classmethod
    def load(cls, dct: Dict[str, Any]) -> Union[SubscribedMessage, Dict[str, Any]]:
        """Load a SubscribedMessage object from a dictionary."""
        if tuple(dct.keys()) == cls._fields:
            return cls(
                dct['channel_id'],
                dct['message_id'],
                dct['members'],
                dct['warnings'],
                dct['stats']
            )
        return dct

    def __eq__(self, comp: object) -> bool:
        if not isinstance(comp, SubscribedMessage):
            return False
        return (
            self.channel_id == comp.channel_id
            and self.message_id == comp.message_id
        )


class TeamData(NamedTuple):
    """Stores the TLA, number of members and presence of a team leader for a team."""

    TLA: str
    members: int = 0
    leader: bool = False

    def has_leader(self) -> bool:
        """Return whether the team has a leader."""
        return self.leader

    def is_primary(self) -> bool:
        """Return whether the team is a primary team."""
        return not self.TLA[-1].isdigit() or self.TLA[-1] == 1

    def school(self) -> str:
        """TLA without the team number."""
        return ''.join(c for c in self.TLA if c.isalpha())

    def __str__(self) -> str:
        data_str = f'{self.TLA:<15} {self.members:>2}'
        if self.leader is False:
            data_str += '  No leader'
        return data_str


class TeamsData(NamedTuple):
    """A container for a list of TeamData objects."""

    teams_data: List[TeamData]

    def gen_team_memberships(self, guild: discord.Guild, leader_role: discord.Role) -> None:
        """Generate a list of TeamData objects for the given guild, stored in teams_data."""
        teams_data = []

        for role in filter(lambda role: role.name.startswith(TEAM_PREFIX), guild.roles):
            team_data = TeamData(
                TLA=role.name[len(TEAM_PREFIX):],
                members=len(list(filter(
                    lambda member: leader_role not in member.roles,
                    role.members,
                ))),
                leader=len(list(filter(
                    lambda member: leader_role in member.roles,
                    role.members,
                ))) > 0,
            )

            teams_data.append(team_data)

        teams_data.sort(key=lambda team: team.TLA)  # sort by TLA
        self.teams_data.clear()
        self.teams_data.extend(teams_data)

    @property
    def empty_tlas(self) -> List[str]:
        """A list of TLAs for teams with no members or leaders."""
        return [
            team.TLA
            for team in self.teams_data
            if not team.leader and team.members == 0
        ]

    @property
    def missing_leaders(self) -> List[str]:
        """A list of TLAs for teams with no leaders but at least one member."""
        return [
            team.TLA
            for team in self.teams_data
            if not team.leader and team.members > 0
        ]

    @property
    def leader_only(self) -> List[str]:
        """A list of TLAs for teams with only leaders and no members."""
        return [
            team.TLA
            for team in self.teams_data
            if team.leader and team.members == 0
        ]

    @property
    def empty_primary_teams(self) -> List[str]:
        """A list of TLAs for primary teams with no members."""
        return [
            team.TLA
            for team in self.teams_data
            if team.is_primary() and team.TLA in self.empty_tlas
        ]

    @property
    def primary_leader_only(self) -> List[str]:
        """A list of TLAs for primary teams with only leaders."""
        return [
            team.TLA
            for team in self.teams_data
            if team.is_primary() and team.TLA in self.leader_only
        ]

    def team_summary(self) -> str:
        """A summary of the teams."""
        return '\n'.join([
            'Members per team',
            *(
                str(team)
                for team in self.teams_data
            )
        ])

    def warnings(self) -> str:
        """A list of warnings for the teams."""
        return '\n'.join([
            f'Empty teams: {len(self.empty_tlas)}',
            f'Teams without leaders: {len(self.missing_leaders)}',
            f'Teams with only leaders: {len(self.leader_only)}',
            '',
            f'Empty primary teams: {len(self.empty_primary_teams)}',
            f'Primary teams with only leaders: {len(self.primary_leader_only)}',
        ])

    def statistics(self) -> str:
        """A list of statistics for the teams."""
        num_teams: int = len(self.teams_data)
        member_counts = [team.members for team in self.teams_data]
        num_members = sum(member_counts)
        num_schools = len([team for team in self.teams_data if team.is_primary()])

        min_team = min(self.teams_data, key=lambda x: x.members)
        max_team = max(self.teams_data, key=lambda x: x.members)

        school_members = defaultdict(list)
        for team in self.teams_data:
            school_members[team.school()].append(team.members)
        school_avg = {school: mean(members) for school, members in school_members.items()}
        max_avg_school, max_avg_size = max(school_avg.items(), key=lambda x: x[1])

        return '\n'.join([
            f'Total teams: {num_teams}',
            f'Total schools: {num_schools}',
            f'Total students: {num_members}',
            f'Max team size: {max_team.members} ({max_team.TLA})',
            f'Min team size: {min_team.members} ({min_team.TLA})',
            f'Average team size: {mean(member_counts):.1f}',
            f'Average school members: {num_members / num_schools:.1f}',
            f'Max team size, school average: {max_avg_size:.1f} ({max_avg_school})',
        ])


class StatBot(commands.Bot):
    """A bot to generate statistics for the discord server."""

    teams_data: TeamsData = TeamsData([])

    async def setup_hook(self):
        """Copies the global commands over to your guild."""
        guild = discord.Object(id=int(os.getenv('DISCORD_GUILD_ID', '0')))
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def on_ready(self) -> None:
        """Print bot information on startup."""
        if self.user is None:
            print('Unable to login to discord')
            await self.close()
        else:
            print('Logged in as')
            print(self.user.name)
            print(self.user.id)
            print('------')
        guild = self.get_guild(int(os.getenv('DISCORD_GUILD_ID', '0')))
        if guild is None:
            print('Unable to find guild')
            await self.close()
            return
        else:
            self.guild = guild

        admin_role = discord.utils.get(self.guild.roles, name=ADMIN_ROLE)
        leader_role = discord.utils.get(self.guild.roles, name=LEADER_ROLE)

        if admin_role is None or leader_role is None:
            print('Unable to find admin or leader role')
            await self.close()
            exit(1)
        else:
            self.admin_role = admin_role
            self.leader_role = leader_role

        self.teams_data.gen_team_memberships(self.guild, self.leader_role)

        if len(sys.argv) > 1 and sys.argv[1] == 'dump':
            print(self.teams_data.team_summary())
            print('------')
            print(self.teams_data.warnings())
            print('------')
            print(self.teams_data.statistics())
            await self.close()
        else:
            await self.update_subscribed_messages()

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Remove subscribed messages by reacting with a cross mark."""
        if payload.emoji.name != '\N{CROSS MARK}':
            return
        if SubscribedMessage(payload.channel_id, payload.message_id) not in SUBSCRIBED_MESSAGES:
            # Ignore for messages not in the subscribed list
            return
        if payload.member is None:
            # Ignore for users not in the server
            return
        if not (await self.is_owner(payload.member) or self.admin_role in payload.member.roles):
            # Ignore for users without admin privileges
            return

        await self.remove_subscribed_message(
            SubscribedMessage(payload.channel_id, payload.message_id),
        )

    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        """Update subscribed messages when a member's roles change."""
        self.teams_data.gen_team_memberships(self.guild, self.leader_role)

        await self.update_subscribed_messages()

    def _save_subscribed_messages(self) -> None:
        """Save subscribed messages to file."""
        with open(SUBSCRIBE_MSG_FILE, 'w') as f:
            json.dump(SUBSCRIBED_MESSAGES, f, default=lambda x: x._asdict())

    def add_subscribed_message(self, msg: SubscribedMessage) -> None:
        """Add a subscribed message to the subscribed list."""
        SUBSCRIBED_MESSAGES.append(msg)
        self._save_subscribed_messages()

    async def remove_subscribed_message(self, msg: SubscribedMessage) -> None:
        """Remove a subscribed message from the channel and subscribed list."""
        msg_channel = await self.fetch_channel(msg.channel_id)
        if not hasattr(msg_channel, 'fetch_message'):
            # ignore for channels that don't support message editing
            return
        message = await msg_channel.fetch_message(msg.message_id)

        print(f'Removing message {message.content[:50]}... from {message.author.name}')
        await message.delete()  # remove message from discord

        # remove message from subscription list and save to file
        SUBSCRIBED_MESSAGES.remove(msg)
        self._save_subscribed_messages()

    async def update_subscribed_messages(self) -> None:
        """Update all subscribed messages."""
        print('Updating subscribed messages')
        for sub_msg in SUBSCRIBED_MESSAGES:  # edit all subscribed messages
            message = self.msg_str(
                sub_msg.members,
                sub_msg.warnings,
                sub_msg.stats
            )
            message = f"```\n{message}\n```"

            try:
                msg_channel = await self.fetch_channel(sub_msg.channel_id)
                if not hasattr(msg_channel, 'fetch_message'):
                    # ignore for channels that don't support message editing
                    continue
                msg = await msg_channel.fetch_message(sub_msg.message_id)
                await msg.edit(content=message)
            except AttributeError:  # message is no longer available
                await self.remove_subscribed_message(sub_msg)

    async def send_response(
        self,
        ctx: discord.Interaction,
        message: str,
    ) -> Optional[discord.Message]:
        """Respond to an interaction and return the bot's message object."""
        try:
            await ctx.response.send_message(f"```\n{message}\n```")
            bot_message = await ctx.original_response()
        except discord.NotFound as e:
            print('Unable to find original message')
            print(e)
        except (discord.HTTPException, discord.ClientException) as e:
            print('Unable to connect to discord server')
            print(e)
        else:
            return bot_message
        return None

    def msg_str(self, members: bool = True, warnings: bool = True, statistics: bool = False) -> str:
        """Generate a message string for the given options."""
        return '\n\n'.join([
            *([self.teams_data.team_summary()] if members else []),
            *([self.teams_data.warnings()] if warnings else []),
            *([self.teams_data.statistics()] if statistics else []),
        ])


intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = StatBot(intents=intents, command_prefix='~')


@bot.tree.command()
@app_commands.describe(
    members='Display the number of members in each team',
    warnings='Display warnings about missing leaders and empty teams',
    stats='Display statistics about the teams',
)
@app_commands.checks.has_role(ADMIN_ROLE)
async def stats(
    ctx: discord.Interaction,
    members: bool = False,
    warnings: bool = False,
    stats: bool = False,
) -> None:
    """Generate statistics for the server and send them to the channel."""
    if (members, warnings, stats) == (False, False, False):
        members = True
        warnings = True
    message = bot.msg_str(members, warnings, stats)

    await bot.send_response(ctx, message)


@bot.tree.command()
@app_commands.describe(
    members='Display the number of members in each team',
    warnings='Display warnings about missing leaders and empty teams',
    stats='Display statistics about the teams',
)
@app_commands.checks.has_role(ADMIN_ROLE)
async def stats_subscribe(
    ctx: discord.Interaction,
    members: bool = False,
    warnings: bool = False,
    stats: bool = False,
) -> None:
    """Subscribe to updates for statistics for the server and send a subscribed message."""
    if (members, warnings, stats) == (False, False, False):
        members = True
        warnings = True
    message = bot.msg_str(members, warnings, stats)

    bot_message = await bot.send_response(ctx, message)
    if bot_message is None:
        return
    bot.add_subscribed_message(SubscribedMessage(
        bot_message.channel.id,
        bot_message.id,
        members,
        warnings,
        stats,
    ))

def load_subscribed_messages() -> None:
    """Load subscribed message details from file."""
    global SUBSCRIBED_MESSAGES
    try:
        with open(SUBSCRIBE_MSG_FILE) as f:
            SUBSCRIBED_MESSAGES = json.load(f, object_hook=SubscribedMessage.load)
    except (json.JSONDecodeError, FileNotFoundError):
        with open(SUBSCRIBE_MSG_FILE, 'w') as f:
            f.write('[]')


def main() -> None:
    """Load environment variables and start the bot."""
    load_dotenv()
    load_subscribed_messages()

    bot.run(os.getenv('DISCORD_TOKEN', ''))


if __name__ == '__main__':
    main()
