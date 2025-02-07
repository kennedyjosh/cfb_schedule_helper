import discord
import json
import logging.handlers
from team_name_standardization import standardize


def _parse_team_from_display_name(display_name):
    return standardize(display_name.split("-")[1].split("(")[0].strip())


class MyClient(discord.Client):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.user_teams = {}  # guild-id : set(str)
        self.state = {}  # guild-id : state  TODO: state enum?

    async def on_ready(self):
        logger.info(f'Logged on as {self.user}!')

        logger.info(f"Inferring user-controlled teams from user names...")
        for guild in self.guilds:
            if guild.id not in self.user_teams:
                self.user_teams[guild.id] = set()
            user_teams = self.user_teams[guild.id]
            for member in guild.members:
                # parse all members except for the bot
                if member.id != self.user.id:
                    if "inactive" in member.name.lower():
                        logger.debug(f"ignoring: {member.display_name}")
                        continue
                    # names are in the style 'Name - Team (Rank#)'
                    team = _parse_team_from_display_name(member.display_name)
                    user_teams.add(team)
            logger.debug(f"teams in {guild.name} ({guild.id}): {user_teams}")

        logger.info("Bot initialized successfully")

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
                logger.info(f"In {before.guild.name} ({guild_id}), {before_team} changed to {after_team}")
            else:
                logger.info(f"No action necessary, team name is the same. "
                      f"Before: {before_team} | After: {after_team}")
        else:
            logger.info(f"No action necessary, display name is the same ({before.display_name})")

    async def on_message(self, message):
        logger.info(f'Message from {message.author}: {message.content}')


if __name__ == "__main__":
    # set up logging
    logger = logging.getLogger('bot')
    logger.setLevel(logging.INFO)
    logging.getLogger('discord.http').setLevel(logging.INFO)

    handler = logging.handlers.RotatingFileHandler(
        filename='logs/discord.log',
        encoding='utf-8',
        maxBytes=32 * 1024 * 1024,  # 32 MiB
        backupCount=5,  # Rotate through 5 files
    )
    dt_fmt = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter('[{asctime}] [{levelname}] {name}:{module}:{funcName}:{lineno} | {message}', dt_fmt, style='{')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # set permissions for discord client
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    # fetch token from secret.json
    SECRET_FILE = "secret.json"
    try:
        with open(SECRET_FILE, "r") as file:
            data = json.load(file)

        token = data.get("token")
        if token is None:
            raise KeyError("'token' key not found in the JSON file.")

    except FileNotFoundError:
        print(f"Error: The file '{SECRET_FILE}' was not found.")
    except json.JSONDecodeError:
        print(f"Error: Failed to parse JSON from '{SECRET_FILE}'.")
    except KeyError as e:
        print(f"Error: {e}")

    # init and run discord client
    client = MyClient(intents=intents)
    client.run(token, log_handler=None)

