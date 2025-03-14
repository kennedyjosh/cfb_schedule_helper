### CFB Schedule Helper Bot

This is a Discord bot that can be used to help schedule out-of-conference games
for users in your online dynasty. The conversational bot will ask you for schedule
information and what the requested games are. It will use this information to create
and optimal schedule, where all requests are filled and each team has the same number
of home and away games in the season.

### How to use

First, on Discord, you must create a token for the bot. Once you have done that,
create a file at the top level of this repository called `secret.json` and provide,
in JSON format, a single element "token" which maps to your token string.

Next, add the Bot to your discord server(s). The bot supports multiple servers at
a time and will attempt to infer team names from the display names used in the
discord server. 

Now, make sure the code is running. Install the necessary packages with 
`pip install -r requirements.txt`. Then, run `python3 run.py`.

When you're ready to start the process, just tag the bot in Discord: `@ScheduleBot`.

### Future work

- Serialize data: in case of error, or just wanting to generate a new schedule,
  save the inputted information so the user only ever enters it once.
- Let users request matchups using the bot.
  - Create custom commands so that users can request games directly through the bot,
    cutting out the middleman (currently someone must track that info manually and
    copy/paste it to the bot).
- Let users request to fill their schedule with other users (or CPUs) if they have not
  requested the maximum amount of games.
- Let users request their bye weeks to be on certain weeks.
- Reduce the chance of back-to-back bye weeks.
- Save data across seasons for "home and home" considerations.
- Testing: write unit tests for internal functions. Currently testing is done in each
  file where the work is implemented, but this is bad practice. 
