import discord
import enum
import re
from sortedcontainers import SortedList
import time
import src.schedule_requests as schedule_requests
from src.team_name_standardization import standardize


class State(enum.Enum):
    READY = 0
    NEED_REQUESTS = 1
    NEED_SCHEDULES = 2


class MyClient(discord.Client):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.user_teams = {}  # guild-id : SortedList(str)
        self.state = {}  # guild-id : dict, with at least "state" : State entry
        # TODO: do something cleaner here
        assert "logger" in kwargs, "Must specify logger"
        self.logger = kwargs["logger"]

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
            if guild.id not in self.user_teams:
                self.user_teams[guild.id] = []
            for member in guild.members:
                # parse all members except for the bot
                if member.id != self.user.id:
                    if "inactive" in member.name.lower():
                        self.logger.debug(f"ignoring: {member.display_name}")
                        continue
                    # names are in the style 'Name - Team (Rank#)'
                    team = _parse_team_from_display_name(member.display_name)
                    self.user_teams[guild.id].append(team)
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
                    await message.channel.send("Hi! Please copy/paste the schedule requests as a single message.\n"
                                        "Please be aware that I will be reading and interpreting all messages "
                                        "in this channel until my work is done, so keep it strictly business.")
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
                if (self.user_teams[guild_id]) == 0:
                    # TODO: calculate optimal matchups and display results
                    ...
                else:
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
                            if week == 16 and team in ["Army", "Navy"]:
                                continue
                            await message.reply(f"Invalid or duplicate week: {week}")
                            await message.channel.send(f"Please re-enter the information for {team}")
                            return
                    self.state[guild_id]["schedule"][team] = schedule
                    if len(self.user_teams[guild_id]) == 0:
                        # All done, now need to process schedules and write back
                        # TODO
                        ...
                    else:
                        next_team = self.user_teams[guild_id].pop(0)
                        self.state[guild_id]["currTeam"] = next_team
                        await message.channel.send(f"{next_team}")
                    return

        self.logger.debug(f'Ignored message from {message.author}: {message.content}')


def _parse_team_from_display_name(display_name):
    return standardize(display_name.split("-")[1].split("(")[0].strip())

