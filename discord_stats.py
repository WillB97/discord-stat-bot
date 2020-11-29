#!/usr/bin/env python
import os
import sys
import json
from dotenv import load_dotenv
import discord
from discord.ext import commands
import discord.utils
from typing import List, Tuple, Optional


# ID of the role assigned to team leaders
LEADER_ROLE = 313317097222569984

# name of the role able to execute the command
ADMIN_ROLE = 'Barber'

# ID of the server to be surveyed
GUILD_ID = 257120601259507712

# prefix of the role to give the user assigned to a team
TEAM_PREFIX = ''

# file to store messages being dynamically updated between reboots
SUBSCRIBE_MSG_FILE = 'subscribed_messages.json'

class SubscribedMessage:
    def __init__(self,channel_id,message_id):
        self.channel_id = channel_id
        self.message_id = message_id
    def __eq__(self,comp):
        return (self.channel_id == comp.channel_id and self.message_id == comp.message_id)

def SubscribedMessage_load(dct):
    if tuple(dct.keys()) == ('channel_id','message_id'):
        return SubscribedMessage(dct['channel_id'],dct['message_id'])
    return dct

class TeamData:
    "Stores the TLA, number of members and presence of a team leader for a team"
    def __init__(self, TLA:str ,members:int=0, leader:bool=False) -> None:
        self.TLA = TLA
        self.members = members
        self.leader = False
    
    def __repr__(self) -> str:
        data_str = f'{self.TLA:<30} {self.members:>2}'
        if self.leader == False:
            data_str += '  No leader'
        return data_str
    
    def has_leader(self) -> bool:
        return self.leader

subscribed_messages:List[SubscribedMessage] = []

class StatBot(commands.Bot):
    teams_data:List[TeamData] = []
    empty_teams:List[TeamData] = []
    missing_leaders:List[TeamData] = []
    leader_only:List[TeamData] = []

    async def on_ready(self) -> None:
        print('Logged in as')
        print(self.user.name)
        print(self.user.id)
        print('------')
        self.admin_role = discord.utils.get(self.get_guild(GUILD_ID).roles,name=ADMIN_ROLE)

        if len(sys.argv) > 1 and sys.argv[1] == 'dump':
            self.gen_team_memberships()
            print(self.team_memberships())
            print('------')
            print(self.team_warnings())
            print('------')
            print(self.team_statistics())
            await self.close()

    async def on_raw_reaction_add(self, payload):
        if not SubscribedMessage(payload.channel_id, payload.message_id) in subscribed_messages:  # is message in subscribed list
            return
        if payload.emoji.name != '\N{CROSS MARK}':
            return
        if not self.admin_role in payload.member.roles:
            return
        msg_channel = await self.fetch_channel(payload.channel_id)
        msg = await msg_channel.fetch_message(payload.message_id)
        await msg.delete()  # remove message
        subscribed_messages.remove(SubscribedMessage(payload.channel_id, payload.message_id))  # remove ID from subscription list
        with open(SUBSCRIBE_MSG_FILE, 'w') as f:
            json.dump(subscribed_messages, f, default=lambda x:x.__dict__)

    async def on_member_update(self, before, after):
        self.gen_team_memberships()
        message = '```\n' + self.msg_str() + '\n```'
        for sub_msg in subscribed_messages: # edit all subscribed messages
            try:
                msg_channel = await self.fetch_channel(sub_msg.channel_id)
                msg = await msg_channel.fetch_message(sub_msg.message_id)
                await msg.edit(content=message)
            except AttributeError:  # message is no longer available
                subscribed_messages.remove(sub_msg)
                with open(SUBSCRIBE_MSG_FILE, 'w') as f:
                    json.dump(subscribed_messages, f, default=lambda x:x.__dict__)

    def gen_team_memberships(self) -> None:
        self.teams_data.clear() # reset list on each invocation
        guild:discord.Guild = self.get_guild(GUILD_ID)
        leader:discord.Role = discord.utils.get(guild.roles, id=LEADER_ROLE)
        for role in [role for role in guild.roles if role.name.startswith(TEAM_PREFIX)]:
            team_data = TeamData(
                TLA = role.name[len(TEAM_PREFIX):],
                # exclude team leaders from the number of members
                members = len([member for member in role.members if leader not in member.roles])
            )
            leaders:List[discord.Member] = [member for member in role.members if leader in member.roles]
            if len(leaders) > 0:
                team_data.leader = True
            self.teams_data.append(team_data)
        
        self.empty_teams = [team for team in self.teams_data if not team.leader and team.members == 0]
        self.leader_only = [team for team in self.teams_data if team.leader and team.members == 0]
        self.missing_leaders = [team for team in self.teams_data if not team.leader and team.members > 0]

    def team_memberships(self) -> str:
        messages:List[str] = ['Members per team']
        for team in self.teams_data:
            messages += [str(team)]
        return '\n'.join(messages)

    def team_warnings(self) -> str:
        messages:List[str] = []
        messages += [f'Empty teams: {len(self.empty_teams)}']
        messages += [f'Teams without leaders: {len(self.missing_leaders)}']
        messages += [f'Teams with only leaders: {len(self.leader_only)}']
        return '\n'.join(messages)
    
    def team_statistics(self) -> str:
        num_teams:int = len(self.teams_data)
        num_members:int = sum([team.members for team in self.teams_data])
        num_schools:int = num_teams

        min_team:Tuple[str,int] = ('',self.teams_data[0].members)  # initial value
        max_team:Tuple[str,int] = ('',0)  # initial value
        for team in self.teams_data:
            # only count the first team from each school
            if team.TLA[-1].isdigit() and team.TLA[-1] != 1:
                num_schools -= 1
            if team.members > max_team[1]:
                max_team = (team.TLA,team.members)
            elif team.members > 0 and team.members < min_team[1]:
                min_team = (team.TLA,team.members)

        avg_team:int = num_members / num_teams
        avg_school:int = num_members / num_schools
        avg_school_team:Tuple[str,float] = ('',0)  # initial value
        last_TLA = ['',0,0]
        for team in self.teams_data:
            if not team.TLA[-1].isdigit():  # single team school
                if team.members > avg_school_team[1]:
                    avg_school_team = (team.TLA,team.members)
            else:  # multi-team school
                if last_TLA[0] != team.TLA[:-1]:
                    avg_members = last_TLA[1]/max(last_TLA[2],1)
                    if avg_members > avg_school_team[1]:
                        avg_school_team = (last_TLA[0],avg_members)
                    last_TLA[1] = 0
                    last_TLA[2] = 0
                last_TLA[0] = team.TLA[:-1]
                last_TLA[1] += team.members
                last_TLA[2] += 1  # accumulate average
        if self.teams_data[-1].TLA[-1].isdigit():  #make sure final team is parsed
            avg_members = last_TLA[1]/max(last_TLA[2],1)
            if avg_members > avg_school_team[1]:
                avg_school_team = (last_TLA[0],avg_members)

        messages:List[str] = []
        messages += [f'Total teams: {num_teams}']
        messages += [f'Total schools: {num_schools}']
        messages += [f'Total students: {num_members}']
        messages += [f'Max team size: {max_team[1]} ({max_team[0]})']
        messages += [f'Min team size: {min_team[1]} ({min_team[0]})']
        messages += [f'Average team size: {avg_team:.1f}']
        messages += [f'Average school members: {avg_school:.1f}']
        messages += [f'Max team size, school average: {avg_school_team[1]:.1f} ({avg_school_team[0]})']
        return '\n'.join(messages)

    def msg_str(self, members=True, warnings=True, statistics=False) -> str:
        messages:List[str] = []
        if members:
            messages += [self.team_memberships()]
            messages += ['']
        if warnings:
            messages += [self.team_warnings()]
            messages += ['']
        if statistics:
            messages += [self.team_statistics()]
            messages += ['']
        return '\n'.join(messages)

    async def send_response(self, ctx, message:str) -> Optional[discord.Message]:
        try:  # send normal message
            bot_message = await ctx.send('```\n' + message + '\n```')
        except discord.Forbidden as e:
            print('Unable to respond to discord channel')
            print(e)
            return None
        except discord.HTTPException as e:
            print('Unable to connect to discord server')
            print(e)
            return None
        return bot_message

    def process_message_options(self,args) -> Tuple[bool,bool,bool]:
        # TODO: add help function for this
        display_membership = False
        display_warnings = False
        display_stats = False
        if not len(args):
            return (True,True,False)
        for arg in args:
            if arg == 'members':
                display_membership = True
            elif arg == 'warnings':
                display_warnings = True
            elif arg == 'stats':
                display_stats = True
        return (display_membership,display_warnings,display_stats)

load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.reactions = True
bot = StatBot(intents=intents, command_prefix='~')

@bot.command()
@commands.has_role(ADMIN_ROLE)
async def stats(ctx,*args):
    bot.gen_team_memberships()
    members,warnings,stats = bot.process_message_options(args)
    message = bot.msg_str(members,warnings,stats)
    await bot.send_response(ctx,message)

@bot.command()
@commands.has_role(ADMIN_ROLE)
async def stats_subscribe(ctx):
    bot.gen_team_memberships()
    message = bot.msg_str()
    bot_message = await bot.send_response(ctx,message)
    if bot_message is None:
        return
    sub_msg = SubscribedMessage(bot_message.channel.id,bot_message.id)
    subscribed_messages.append(sub_msg)
    with open(SUBSCRIBE_MSG_FILE, 'w') as f:
        json.dump(subscribed_messages, f, default=lambda x:x.__dict__)

try:
    with open(SUBSCRIBE_MSG_FILE) as f:
        subscribed_messages = json.load(f, object_hook=SubscribedMessage_load)
except (json.JSONDecodeError, FileNotFoundError) as e:
    with open(SUBSCRIBE_MSG_FILE, 'w') as f:
        f.write('[]')

bot.run(os.getenv('DISCORD_TOKEN'))
