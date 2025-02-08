import re
from src.team_name_standardization import standardize


def parse(msg, logger):
    """
    The schedule request will come as one long string. Here are the formatting rules:
    1. Lines that start with a number indicate that the following lines are that team's requests.
        ex: 1. Clemson
    2. Requests must include, at minimum, the team name.
        ex: Rutgers
      Additionally, a home/away preference can be specified in parentheses after the team name.
        ex: Rutgers (Home)
      If the home/away preference is in brackets, this will override any home/away balancing to force the preference.
        ex: Rutgers [Home]
    3. A blank line separates one team from the next.
    4. All symbols (besides parentheses for home/away preference) will be ignored.

    This function will return one of two tuples:
      True, results
      False, errors
    """
    currTeam = None
    result = {}  # team : [ {opponent: bool or None} ]  # opponent team is string, prefer home is value
    errors = {}  # team : [ {'opponent': str (required), 'reason': str (required)} ]

    for line in msg.split('\n'):
        line = line.strip()
        # This line means a new team is starting
        if match := re.match(r"^\d+\.\s*(.+)", line):
            try:
                currTeam = standardize(match.group(1))
            except ValueError as e:
                return False, {match.group(1): [{"opponent": "N/A", "reason": "Could not figure out what team this is"}]}
            if currTeam not in result:
                result[currTeam] = {}

        # If the line is blank, the currTeam has finished
        elif line == '':
            currTeam = None

        # If there is a currTeam, then the line contains the name of a desired matchup
        elif currTeam is not None:
            if match := re.match(r"^([^(]+)(?:\s*\(([^)]+)\))?$", line):
                try:
                    team = standardize(match.group(1))
                except ValueError:
                    if currTeam not in errors:
                        errors[currTeam] = []
                    errors[currTeam].append({"opponent": match.group(1),
                                             "reason": f"Could not figure out what team this is: {match.group(1)}"})
                    continue
                if (home_or_away := match.group(2)) is not None:
                    home_or_away = home_or_away.strip().lower()
                    if home_or_away == "home":
                        home = True
                    elif home_or_away == "away":
                        home = False
                    else:
                        if currTeam not in errors:
                            errors[currTeam] = []
                        errors[currTeam].append({"opponent": team,
                                                 "reason": "Only put \"home\" or \"away\" in the parentheses"})
                        continue
                else:
                    home = None
                result[currTeam][team] = home
            else:
                if currTeam not in errors:
                    errors[currTeam] = []
                errors[currTeam].append({"opponent": "N/A",
                                         "reason": f"Badly formatted: {line}"})

    if len(errors.keys()) > 0:
        return False, errors
    else:
        return True, result


def validate(d):
    """
    Validates the results of `parse`:
    1. Each team has at most 4 requests
    2. All requests are mirrored by the other team. If one team has no records at all, this is not
       considered an error, but d will be modified to hold perfectly mirrored records.
    3. Home/away preferences compliment each other. If only one team has a preference, d will
       be updated for the other team to show the opposite preference

    Returns True, d if the dict is valid – d may have been edited, but the fixes caused no conflict
    Return False, errors if dict is not valid, where errors is a list of error messages
    """
    errors = []
    to_add = {}
    for team in d:
        for opp in d[team]:
            # Check if the other team even exists in the dict
            if opp not in d:
                if opp not in to_add:
                    to_add[opp] = {}
                to_add[opp][team] = not d[team][opp] if d[team][opp] is not None else None
            else:
                # Check if other team has record of the matchup
                if team not in d[opp]:
                    errors.append(f"{team} has {opp} as an opponent, but {opp} doesn't have {team} listed")
                else:
                    # Check if there is a home/away preference, and if they compliment each other
                    if d[team][opp] == d[opp][team] and d[team][opp] is not None:
                        # They have the same non-None preference
                        errors.append(f"{team} and {opp} both prefer to be {'home' if d[team][opp] else 'away'}")
                    elif d[team][opp] is None:
                        # team has no pref, but opp does
                        d[team][opp] = not d[opp][team]
                    elif d[opp][team] is None:
                        # opp has no pref, team does
                        d[opp][team] = not d[team][opp]

    if len(errors) > 0:
        return False, errors
    else:
        for team in to_add:
            d[team] = to_add[team]
        return True, d

