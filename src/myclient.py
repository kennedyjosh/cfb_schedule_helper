import discord
import enum
import re
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
        self.user_teams = {}  # guild-id : set(str)
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
                self.user_teams[guild.id] = set()
            user_teams = self.user_teams[guild.id]
            for member in guild.members:
                # parse all members except for the bot
                if member.id != self.user.id:
                    if "inactive" in member.name.lower():
                        self.logger.debug(f"ignoring: {member.display_name}")
                        continue
                    # names are in the style 'Name - Team (Rank#)'
                    team = _parse_team_from_display_name(member.display_name)
                    user_teams.add(team)
            if guild.id not in self.state:
                self.state[guild.id] = {}
            self.state[guild.id]["state"] = State.READY
            self.logger.info(f"teams in {guild.name} ({guild.id}): {user_teams}")

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
        guild_id = message.guild.id
        state = self.state[guild_id]["state"]
        if state == State.READY:
            # In this state, the bot is alive but hasn't been called upon yet.
            # Wait for a commish to tag the bot
            if "Commish" in [role.name for role in message.author.roles]:
                if match := re.match(r"\s*<@(\d+)>\s*", message.content):
                    id = match.group(1)
                    if int(id) == self.user.id:
                        next_state = State.NEED_REQUESTS
                        self.logger.info(f"{_parse_team_from_display_name(message.author.display_name)} tagged me, "
                                         f"updating state to {next_state}")
                        self.state[guild_id]["state"] = next_state
                        self.state[guild_id]["commish"] = message.author.id
                        await message.reply("Hi! Please copy/paste the schedule requests as a single message.")
                        return
        elif state == State.NEED_REQUESTS:
            # In this state, it is time to process the schedule requests
            # It should be one long message from the same person who initiated the process
            if message.author.id == self.state[guild_id]["commish"]:
                status, result = schedule_requests.parse(message.content, self.logger)
                if status is False:
                    # There was some error during processing, tell user
                    self.logger.error(f"Error parsing schedule requests: {result}")
                    msg = f"Seems like there are some formatting error(s). Details:\n"
                    for team in result:
                        msg += f"Under {team}:\n"
                        for problem in result[team]:
                            msg += f"\t{problem['opponent']}: {problem['reason']}\n"
                    await message.channel.send(msg)
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
                    await message.channel.send(msg)
                    time.sleep(1)
                    await message.channel.send("Please remedy the problems and then "
                                               "copy/paste the schedule requests again.")
                    return

                next_state = State.NEED_SCHEDULES
                self.logger.info(f"Scheduling requests successfully parsed and validated, updating state to {next_state}")
                self.schedule_requests = result
                self.state[guild_id]["state"] = next_state
                await message.channel.send("Great! Now, I need to know more about some teams' schedules.")
                ## TODO: next step: ask questions about schedules

        elif state == State.NEED_SCHEDULES:
            # TODO
            ...

        self.logger.debug(f'Ignored message from {message.author}: {message.content}')


def _parse_team_from_display_name(display_name):
    return standardize(display_name.split("-")[1].split("(")[0].strip())

