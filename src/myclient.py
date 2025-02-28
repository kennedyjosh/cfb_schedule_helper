import discord
import enum
import re
import time
import src.schedule_requests as schedule_requests
import src.scheduler as scheduler
from src.team_name_standardization import standardize


class State(enum.Enum):
    READY = 0
    NEED_REQUESTS = 1
    NEED_SCHEDULES = 2
    READ_SCHEDULES = 3
    FAILED = 4


class MyClient(discord.Client):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ignored_users = {}  # guild_id : list
        self.user_teams = {}  # guild-id : SortedList(str)
        self.state = {}  # guild-id : dict, with at least "state" : State entry
        # TODO: do something cleaner here
        assert "logger" in kwargs, "Must specify logger"
        self.logger = kwargs["logger"]

    def _scrape_teams(self, guild_id, members=None):
        if members is None:
            # Need to find guild with that id and fetch the members manually
            guild = [g for g in self.guilds if g.id == guild_id]
            if len(guild) != 0:
                raise ValueError(f"Bad guild id: {guild_id}")
            members = guild[0].members
        self.user_teams[guild_id] = []
        self.ignored_users[guild_id] = []
        for member in members:
            # parse all members except for the bot
            if member.id != self.user.id:
                if "inactive" in member.display_name.lower():
                    self.logger.debug(f"ignoring: {member.display_name}")
                    self.ignored_users[guild_id].append(member.display_name)
                    continue
                # names are in the style 'Name - Team (Rank#)'
                try:
                    team = _parse_team_from_display_name(member.display_name)
                except IndexError:
                    self.logger.error(f"Unexpected member name: {member.display_name}")
                    team = None
                if team == None:
                    self.logger.warning(f"Unable to process team for user: {member.display_name}")
                    self.ignored_users[guild_id].append(member.display_name)
                    continue
                self.user_teams[guild_id].append(team)

    async def on_error(self, event, *args, **kwargs):
        """
        For errors that occur during one of the client functions
        """
        self.logger.error(f"Unhandled error in {event}", exc_info=True)
        # logger.error(traceback.format_exc())

    async def on_ready(self):
        self.logger.info(f'Logged on as {self.user}!')

        self.logger.info(f"Inferring user-controlled teams from user names...")
        for guild in self.guilds:
            self._scrape_teams(guild.id, members=guild.members)
            if guild.id not in self.state:
                self.state[guild.id] = {}
            self.state[guild.id]["state"] = State.READY
            self.logger.info(f"teams in {guild.name} ({guild.id}): {self.user_teams[guild.id]}")

        self.logger.info("Bot initialized successfully")

    async def on_member_update(self, before, after):
        """
        If a member updates their info, check to see if it was a team name change.
        If it is, update self.user_teams
        """
        if before.display_name != after.display_name:
            before_team = _parse_team_from_display_name(before.display_name)
            after_team = _parse_team_from_display_name(after.display_name)
            if before_team != after_team:
                guild_id = before.guild.id
                self.user_teams[guild_id].remove(before_team)
                self.user_teams[guild_id].add(after_team)
                self.logger.info(f"In {before.guild.name} ({guild_id}), {before_team} changed to {after_team}")
            else:
                self.logger.info(f"No action necessary, team name is the same. "
                      f"Before: {before_team} | After: {after_team}")
        else:
            self.logger.info(f"No action necessary, display name is the same ({before.display_name})")

    async def on_message(self, message):
        try:
            await self.handle_message(message)
        except:
            if self.state[message.guild.id]["state"] != State.FAILED:
                await message.channel.send(f"Oh no! I have experienced a fatal error and will need "
                                           f"to be manually restarted.")
                self.logger.error(f"Fatal error on guild: {message.guild.name} ({message.guild.id})")
                self.state[message.guild.id]["state"] = State.FAILED


    async def handle_message(self, message):
        # Quick return if the message is coming from itself
        if message.author.id == self.user.id:
            return
        guild_id = message.guild.id
        state = self.state[guild_id]["state"]
        if state == State.READY:
            # In this state, the bot is alive but hasn't been called upon yet.
            if match := re.match(r"\s*<@(\d+)>\s*", message.content):
                id = match.group(1)
                if int(id) == self.user.id:
                    next_state = State.NEED_REQUESTS
                    self.logger.info(f"{_parse_team_from_display_name(message.author.display_name)} tagged me, "
                                     f"updating state to {next_state}")
                    self.state[guild_id]["state"] = next_state
                    self.state[guild_id]["channel"] = message.channel.id
                    await message.channel.send(f"Hi!")
                    if self.ignored_users[guild_id]:
                        time.sleep(1)
                        await message.channel.send(f"I've taken a look at the members in this server, and was "
                                                   f"able to infer a team from everybody except for: "
                                                   f"{', '.join(self.ignored_users[guild_id][:-1]) + ' and ' +
                                                      self.ignored_users[guild_id][-1]}")
                    time.sleep(1)
                    await message.channel.send("Please be aware that I will be reading and interpreting all "
                                               "messages in this channel until my work is done, so keep it "
                                               "strictly business.")
                    time.sleep(1)
                    await message.channel.send("Let's start with the schedule requests. "
                                               "Please copy/paste them as a single message.")

                    return
        elif state == State.NEED_REQUESTS:
            # In this state, it is time to process the schedule requests
            if message.channel.id == self.state[guild_id]["channel"]:
                status, result = schedule_requests.parse(message.content, self.logger)
                if status is False:
                    # There was some error during processing, tell user
                    self.logger.error(f"Error parsing schedule requests: {result}")
                    msg = f"Seems like there are some formatting error(s). Details:\n"
                    for team in result:
                        msg += f"Under {team}:\n"
                        for problem in result[team]:
                            msg += f"\t{problem['opponent']}: {problem['reason']}\n"
                    await message.reply(msg)
                    time.sleep(1)
                    await message.channel.send("Please correct the errors and then "
                                               "copy/paste the schedule requests again.")
                    return

                # Validate the results
                status, result = schedule_requests.validate(result)
                if status is False:
                    self.logger.error(f"Errors while validating schedule request logic: {result}")
                    msg = (f"There are validation errors with the scheduling requests. "
                           f"Please double check on the following:\n")
                    for err in result:
                        msg += f"* {err}\n"
                    await message.reply(msg)
                    time.sleep(1)
                    await message.channel.send("Please remedy the problems and then "
                                               "copy/paste the schedule requests again.")
                    return

                if result == {}:
                    # Probably the wrong thing was pasted in, let them try again
                    await message.reply(f"I didn't understand this message.")
                    await message.channel.send("Please send the schedule requests again.")
                    return

                next_state = State.NEED_SCHEDULES
                self.logger.info(f"Scheduling requests successfully parsed and validated, updating state to {next_state}")
                self.state[guild_id]["state"] = next_state
                self.state[guild_id]["requests"] = result
                self.state[guild_id]["schedule"] = {}
                await message.channel.send("Great! Now, I need to know more about some teams' schedules.")
                time.sleep(2)
                await message.channel.send("I will list teams; for each team, provide a list of numbers representing "
                                           "the weeks that they have conference games scheduled. At the end of this "
                                           "list, include a final number which is the number of home games for that "
                                           "team.")
                time.sleep(1)
                await message.channel.send("For example: \"4 5 6 8 9 10 11 13 6\" indicates a team has conference "
                                           "games in weeks 4-6, 8-11, and 13, and that 6 of them are home games.")
                time.sleep(2)
                await message.channel.send("Okay, here we go. I'm going to list a team and then wait for your reply.")
                team = self.user_teams[guild_id].pop(0)
                self.state[guild_id]["currTeam"] = team
                await message.channel.send(team)
                return
                ## TODO: if user makes an error, allow them to go back to the previous team and redo it

        elif state == State.NEED_SCHEDULES:
            state = self.state[guild_id]
            if message.channel.id == self.state[guild_id]["channel"]:
                # Process the existing schedule for a team
                team = state["currTeam"]
                schedule = {"balance": 0, "free_weeks": list(range(0, 15))}
                msg = message.content.split(" ")
                try:
                    msg = [int(e.strip()) for e in msg]
                except ValueError:
                    await message.reply("Please be sure to only type numbers")
                    await message.channel.send(f"Please re-enter the information for {team}")
                    return
                schedule["balance"] = msg[-1] - (len(msg) - msg[-1] - 1)
                for week in msg[:-1]:
                    try:
                        schedule["free_weeks"].remove(week)
                    except:
                        if week == 14 and team in ["Army", "Navy"]:
                            continue
                        await message.reply(f"Invalid or duplicate week: {week}")
                        await message.channel.send(f"Please re-enter the information for {team}")
                        return
                self.state[guild_id]["schedule"][team] = schedule
                if len(self.user_teams[guild_id]) == 0:
                    # All done, now need to process schedules and write back
                    await message.channel.send("Okay, now give me some time to calculate an optimal schedule.")
                    # First, though, remove teams from requests and schedule
                    starting_schedules = self.state[guild_id]["schedule"]
                    for team in (requests := self.state[guild_id]["requests"]):
                        if len(requests[team]) == 0:
                            del requests[team]
                        if team in starting_schedules and len(starting_schedules[team]) == 0:
                            del starting_schedules[team]
                    # Call scheduler and process results
                    schedule, homeGames, cpuGames, errors = scheduler.do_schedule(requests, starting_schedules, max_iter=100000)
                    # Separate into matchmaking errors and home/away balance errors
                    schedule_errors = {}
                    balance_errors = {}
                    for error in errors:
                        if type(error) is tuple:
                            schedule_errors[error] = errors[error]
                        else:
                            balance_errors[error] = errors[error]
                    self.state[guild_id]["schedule"] = schedule
                    self.state[guild_id]["home"] = homeGames
                    self.state[guild_id]["cpu"] = cpuGames
                    next_state = State.READ_SCHEDULES
                    self.logger.info(f"Processed schedule, changing state to {next_state}")
                    self.logger.debug(f"schedule: {schedule}")
                    self.logger.debug(f"homeGames: {homeGames}")
                    self.logger.debug(f"cpuGames: {cpuGames}")
                    self.logger.debug(f"errors: {errors}")
                    self.state[guild_id]["state"] = next_state
                    self.state[guild_id]["seen_teams"] = set()
                    time.sleep(1)
                    await message.channel.send(f"Okay, I have the schedule.\n")
                    if schedule_errors or balance_errors:
                        time.sleep(1)
                        await message.channel.send(f"Unfortunately, given all the requests and the locked "
                                                   f"conference schedules, it was not possible to make a "
                                                   f"perfect schedule.\n")
                        if not schedule_errors:
                            time.sleep(1)
                            await message.channel.send(f"Thankfully, I was able to fill all the requests, I just "
                                                       f"couldn't give everyone a perfectly balanced schedule.")
                        if not balance_errors:
                            time.sleep(1)
                            await message.channel.send("Unfortunately, I was unable to fulfill all the scheduling "
                                                       "requests. On the bright side, I was able to give everyone "
                                                       "a perfectly balanced home/away slate.")
                        time.sleep(1)
                        msg = "Here are the issues with the schedule I created:\n"
                        for error in schedule_errors:
                            msg += (f"* {error[0]} vs {error[1]} couldn't be scheduled as they didn't have "
                                    f"enough weeks in common.\n")
                        for error in balance_errors:
                            bal = balance_errors[error]
                            msg += (f"* {error} has an unbalanced schedule with {abs(bal)} "
                                    f"more {'home' if bal > 0 else 'away'} game{'s' if abs(bal) != 1 else ''} "
                                    f"than they would ideally have.\n")
                        await message.channel.send(msg)
                        time.sleep(1)
                    time.sleep(1)
                    await message.channel.send("Now, I'll tell you the schedule one team at a time. You just "
                                               "tell me the team and I'll give you their schedule. Ready? Go! ")
                    return
                else:
                    next_team = self.user_teams[guild_id].pop(0)
                    self.state[guild_id]["currTeam"] = next_team
                    await message.channel.send(f"{next_team}")
                return

        elif state == State.READ_SCHEDULES:
            if message.channel.id == self.state[guild_id]["channel"]:
                try:
                    team = standardize(message.content.strip())
                except ValueError:
                    await message.reply(f"I'm not sure what team that is, could you spell it out more plainly?")
                    return
                schedule = self.state[guild_id]["schedule"]
                if team not in schedule:
                    await message.reply(f"This team didn't have any requests, and therefore, I did not "
                                        f"build a schedule for them. You will have to give them CPU games "
                                        f"and balance the home/away yourself.")
                    return
                schedule = schedule[team]
                homeGames = self.state[guild_id]["home"][team]
                cpuGames = self.state[guild_id]["cpu"][team]
                msg = f"Schedule details for {team}:\n"
                schedule_tuples = sorted([(v, k) for k,v in schedule.items()])
                for week, opponent in schedule_tuples:
                    msg += f"* Week {week} {'vs' if homeGames[opponent] else 'at'} {opponent}\n"
                if sum(cpuGames.values()) > 0:
                    msg += "Additionally, schedule "
                    tmp_str = [f"{n} {setting} CPU game{'s' if n != 1 else ''}" for n, setting in
                               [(int(cpuGames[k]), k) for k, v in cpuGames]]
                    if int(cpuGames["home"]) != cpuGames["home"]:
                        # Test to see if there is a 0.5 in the dict values - if so, the game can be home or away
                        tmp_str.append(f"1 CPU game that can be either home or away")
                    msg += ', '.join(tmp_str[:-1]) + " and " + tmp_str[-1] + ".\n"

                time.sleep(1)
                self.state[guild_id]["seen_teams"].add(team)
                if len(self.state[guild_id]["seen_teams"]) == len(self.state[guild_id]["schedule"]):
                    await message.channel.send("That's all the teams. My work here is done. To restart "
                                               "the process, just tag me again.")
                    next_state = State.READY
                    self.logger.info(f"Finished, resetting state to {next_state}")
                    self.state[guild_id] = {"state": next_state}
                    self._scrape_teams(guild_id)
                else:
                    await message.channel.send("What's the next team you'd like to see the schedule for?")
                return


        self.logger.debug(f'Ignored message from {message.author}: {message.content}')


def _parse_team_from_display_name(display_name):
    try:
        return standardize(display_name.split("-")[1].split("(")[0].strip())
    except ValueError:
        return None

