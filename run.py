import discord
import json
import logging.handlers
import sys
from src.myclient import MyClient


if __name__ == "__main__":
    # set up logging
    logger = logging.getLogger('bot')
    logger.setLevel(logging.DEBUG)
    logging.getLogger('discord.http').setLevel(logging.DEBUG)

    # for errors that go to stderr
    # https://stackoverflow.com/a/31688396/11106258
    class LoggerWriter:
        def __init__(self, level):
            # self.level is really like using log.debug(message)
            # at least in my case
            self.level = level

        def write(self, message):
            # if statement reduces the amount of newlines that are
            # printed to the logger
            if message != '\n':
                self.level(message)

        def flush(self):
            # create a flush method so things can be flushed when
            # the system wants to. Not sure if simply 'printing'
            # sys.stderr is the correct way to do it, but it seemed
            # to work properly for me.
            self.level(sys.stderr)

    sys.stderr = LoggerWriter(logger.error)

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
    client = MyClient(intents=intents, logger=logger)
    client.run(token, log_handler=None)

