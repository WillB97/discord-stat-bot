#!/usr/bin/env python
import os
import sys
from dotenv import load_dotenv
import discord
from discord.ext import commands
import discord.utils
from typing import List, Tuple


# ID of the role assigned to team leaders
LEADER_ROLE = 313317097222569984

# name of the role able to execute the command
ADMIN_ROLE = 'Barber'

# ID of the server to be surveyed
GUILD_ID = 257120601259507712

# prefix of the role to give the user assigned to a team
TEAM_PREFIX = ''


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

        if len(sys.argv) > 1 and sys.argv[1] == 'dump':
            self.gen_team_memberships()
            print(self.team_memberships())
            print('------')
            print(self.team_warnings())
            print('------')
            print(self.team_statistics())
            await self.close()

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
        avg_school_team:int = 0
        #TODO: max avg team size per school

        messages:List[str] = []
        messages += [f'Total teams: {num_teams}']
        messages += [f'Total schools: {num_schools}']
        messages += [f'Max team size: {max_team[1]} ({max_team[0]})']
        messages += [f'Min team size: {min_team[1]} ({min_team[0]})']
        messages += [f'Average team size: {avg_team:.1f}']
        messages += [f'Average school members: {avg_school:.1f}']
        # messages += [f'Average school team size: {avg_school_team}']
        return '\n'.join(messages)


load_dotenv()

intents = discord.Intents.default()
intents.members = True
bot = StatBot(intents=intents, command_prefix='~')

@bot.command()
@commands.has_role(ADMIN_ROLE)
async def stats(ctx):
    bot.gen_team_memberships()
    messages:List[str] = ['```']
    messages += [bot.team_memberships()]
    messages += [' ']
    messages += [bot.team_warnings()]
    messages += ['```']
    try:
        await ctx.send('\n'.join(messages))
    except discord.Forbidden as e:
        print('Unable to respond to discord channel')
        print(e)
    except discord.HTTPException as e:
        print('Unable to connect to discord server')
        print(e)

bot.run(os.getenv('DISCORD_TOKEN'))
