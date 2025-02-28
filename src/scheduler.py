from copy import deepcopy
from queue import PriorityQueue
import random
from sortedcontainers import SortedList


def _matchup(t1, t2):
     return (min(t1, t2), max(t1, t2))


# This should be the only function called from here
def do_schedule(requests, schedule_info, max_iter=1000):
    """
    This function will take scheduling requests and current unchangeable schedule information
    and attempt to satisfy all requests for each team.

    Approach: Match teams by matching the two teams with the most constraints wrt free weeks.

    `requests`: { team: { opponent: bool or None } }
    `schedule`: { team: { "balance": int, "free_weeks": list(int) } }
    returns: a tuple with a dict of scheduled weeks, a dict of home/away settings,
             a dict of what each teams' CPU schedule needs to be, and a dict of matches unable to be scheduled
             ( { team: { opponent: week }, { team: { opponent: isTeamHomeBool } },
             { team: {'home': int, 'away': int} },  { matchupOrTeam: reason } )
    """
    # Note: teams with no requests should be removed from the inputs prior to reaching this function

    # Though the functions called are optimized to find the best schedules possible,
    # it is very common for two paths to seem equally optimal. Thus, we inject some
    # random element for when two teams are otherwise at equal footing. This can help
    # generate alternate possibilities.

    # An optimal schedule is one where all requests are fulfilled.
    # Try generating different schedules until the optimal schedule is found.
    optimal_schedule_found = False
    curr_iter = 0
    best_schedule = None
    best_schedule_errors = None
    best_error = float("inf")
    best_seed = None
    while not optimal_schedule_found and curr_iter < max_iter:
        schedule, errors = find_schedule(deepcopy(requests), schedule_info, seed=curr_iter)
        if (num_errors := len(errors)) < best_error:
            best_schedule = schedule
            best_schedule_errors = errors
            best_seed = curr_iter
            best_error = num_errors
            if num_errors == 0:
                optimal_schedule_found = True
        curr_iter += 1
    print(f"Best schedule found with error={len(best_schedule_errors)} at seed={best_seed}")

    # Need to update free_weeks for next function
    info = deepcopy(schedule_info)
    for team in info:
        for opp in schedule[team]:
            info[team]["free_weeks"].remove(schedule[team][opp])

    # Try generating different home/away splits to find the one with the best overall balance
    optimal_balance_found = False
    curr_iter = 0
    best_games = [None, None]
    best_balance_errors = None
    best_error = float("inf")
    best_seed = None
    while not optimal_balance_found and curr_iter < max_iter:
        homeGames, cpuGames, errors = set_game_locations(deepcopy(schedule), deepcopy(info), deepcopy(requests), seed=curr_iter)
        error = math.sqrt(sum([x ** 2 for x in errors.values()]))
        if error < best_error:
            best_games = [homeGames, cpuGames]
            best_balance_errors = errors
            best_error = error
            best_seed = curr_iter
            if error == 0:
                optimal_balance_found = True
        curr_iter += 1
    print(f"Best balance found with error={best_error} at seed={best_seed}")

    errors = best_schedule_errors | best_balance_errors
    return best_schedule, best_games[0], best_games[1], errors


def find_schedule(requests, current_schedules, seed=None):
    """
    This function takes schedule requests and current schedule information
    and attempts to find a week for all requests to be fulfilled.
    The `requests` parameter will be modified, so it is recommended to pass a copy.
    Returns a tuple with results and any errors: ( { team: { opponent: week } }, { matchupTuple: descriptionString } )
    """
    # First, go through each matchup, and calculate the list of common weeks when both teams are free.
    # Insert these matchups into a priority queue sorted by number of common free weeks minus
    # the number of desired matchups for the team requesting the most opponents.
    # This will prioritize teams with the busiest schedules and matchups witht the least number of common weeks.
    seen = set()  # tuples of matchup teams in alpha order (use _matchup function)
    common_free_weeks = {}  # the matchup tuple will be the key, list of common free weeks the value
    priority_dict = {}  # track the priority of each matchup, they will be updated later
    seeds = {}  # track random seed generated for each matchup, in case we need to remove and reinsert to the pq later
    pq = PriorityQueue()
    for team in requests:
        for opp in requests[team]:
            matchup = _matchup(team, opp)
            if matchup in seen:
                continue
            free_weeks_intersection = SortedList(
                set(current_schedules[team]["free_weeks"]) & set(current_schedules[opp]["free_weeks"])
            )
            common_free_weeks[matchup] = free_weeks_intersection
            priority = len(free_weeks_intersection) - max(len(requests[team]), len(requests[opp]))
            priority_dict[matchup] = priority
            seed = random.random() if seed is not None else 0
            seeds[matchup] = seed
            pq.put((priority, seed, matchup))
            seen.add(matchup)

    # Now, go through the priority queue.
    # For each team in that matchup, gather their common free weeks with their other desired opponents.
    # Choose a random week such that
    #  1. It is in the common weeks of the two teams in the matchup
    #  2. It appears the least out of all the common weeks with other desired opponents for both teams
    # The theory is to schedule based on the week with the least possibilites outside this matchup
    schedule = {}
    errors = {}
    while not pq.empty():
        # Chose a week to schedule a matchup
        _, _, matchup = pq.get()
        common_weeks = common_free_weeks[matchup]
        common_weeks_count = {week: 0 for week in common_weeks}  # maintain count of opponents also free these weeks
        for team in matchup:
            for opp in requests[team]:
                other_matchup = _matchup(team, opp)
                if matchup == other_matchup:
                    continue
                intersection = list(set(common_weeks) & set(common_free_weeks[other_matchup]))
                for week in intersection:
                    common_weeks_count[week] += 1
        least_common_weeks = [k for k, v in common_weeks_count.items() if v == min(common_weeks_count.values())]
        try:
            chosen_week = random.choice(least_common_weeks)
        except IndexError:
            # If a week cannot be chosen here, the matchup cannot be scheduled
            errors[matchup] = "No overlapping free weeks"

        # Add the scheduled matchup to result
        if matchup[0] not in schedule:
            schedule[matchup[0]] = {}
        schedule[matchup[0]][matchup[1]] = chosen_week
        if matchup[1] not in schedule:
            schedule[matchup[1]] = {}
        schedule[matchup[1]][matchup[0]] = chosen_week

        # Remove each team from the others' requests, as it is now scheduled
        del requests[matchup[0]][matchup[1]]
        del requests[matchup[1]][matchup[0]]

        # Now that the week is chosen, remove it from common weeks for these two teams other matchups
        for team in matchup:
            for opp in requests[team]:
                other_matchup = _matchup(team, opp)
                if matchup == other_matchup:
                    continue
                if chosen_week in common_free_weeks[other_matchup]:
                    common_free_weeks[other_matchup].remove(chosen_week)
                    # We must now recalculate this matchup's spot in the priority queue and update it
                    new_priority = len(common_free_weeks[other_matchup]) - max(len(requests[team]), len(requests[opp]))
                    new_seed = random.random() if seed is not None else 0
                    pq.queue.remove((priority_dict[other_matchup], seeds[other_matchup], other_matchup))
                    priority_dict[other_matchup] = new_priority
                    seeds[other_matchup] = new_seed
                    pq.put((new_priority, new_seed, other_matchup))

    return schedule, errors


def set_game_locations(schedule, info, preferences, respect_preferences=True, seed=None):
    """
    This function will take a schedule and the remaining free weeks for each team and
    decide the location of all games, trying to maintain balance. If it can, it will keep
    home/away preferences. The returned data will be a dict specifying whether each opponent is
    a home game or not plus another dict explaining how many and where the CPU games need to be.
    The `schedule` and `info` parameters may be modified, so it is recommended to pass a copy.
    If `respect_preferences` is true, the algorithm will try to take into account home/away preferences.
    If `seed` is given, it will add some random element to tiebreaker when 2 teams are in an identical siutation.

    `schedule`: { team : { opponent : week } }
    `info`: `schedule`: { team: { "balance": int, "free_weeks": list(int) } }
    `preferences`: { team: { opponent: bool or None } }
    `respect_preferences`: bool
    `seed`: int or None
    returns: a tuple with a dict of home/away settings,  a dict of what each teams' CPU schedule
             needs to be, and a dict of any unbalanced schedules
             ( { team: { opponent: isTeamHomeBool } }, { team: {'home': int, 'away': int} },
              { team: balance })
    """
    if seed:
        random.seed(seed)
    # Pre-processing: for free-weeks (in info dict) we only care how many there are, not what they are
    for team in info:
        info[team]["free_weeks"] = len(info[team]["free_weeks"])

    # Want to process teams in order of how unbalanced their schedule is and how many user games they have.
    # Use priority queue: -1 * ( abs(balance) + num_user_games
    pq = PriorityQueue()
    settings = {}
    cpuGames = {}
    seeds = {}
    for team in schedule:
        seeds[team] = random.random() if seed else 0
        if info[team]["balance"] != 0:
            pq.put((-1 * (info[team]["balance"] + len(schedule[team])), seeds[team], team))
        settings[team] = {}
        cpuGames[team] = {"home": 0, "away": 0}

    # Now, process each team from the priority queue.
    # The general approach is going to take the minimum number of actions
    # to balance a team's schedule. Ideally, at the end of this step, teams will all have a balance
    # of 0, even if they still have games left to decide the setting of.
    # Approach:
    #  1. Try and balance schedule using CPU games
    #  2. Try and balance schedule using user games: schedule user who is most unbalanced in the opposite
    #     direction, first
    # Be sure to re-calculate team priorities and re-insert them into the priority queue when needed.
    errors = {}
    while not pq.empty():
        _, _, team = pq.get()
        init_balance = info[team]["balance"]
        abs_init_balance = abs(init_balance)
        init_num_user_games = len(schedule[team])
        num_cpu_games = info[team]["free_weeks"] - 3  # there are exactly 3 bye weeks for each team
        adjustment = 1 if init_balance < 0 else -1  # adjustment = 1 to add home games, -1 to add away games
        # First, try and use CPU games to balance the schedule
        if num_cpu_games > 0:
            setting = "home" if adjustment == 1 else "away"
            if num_cpu_games <= abs_init_balance:
                # Use CPU gqmes to try and balance
                num_games = min(num_cpu_games, abs_init_balance)
                cpuGames[team][setting] += num_games
                # Adjust info dict to reflect added CPU games
                info[team]["balance"] += (adjustment * num_games)
                info[team]["free_weeks"] -= num_games
        # Now, try to balance with user games, starting with users who are most unbalanced in the opposite direction
        balance = info[team]["balance"]
        if balance == 0: continue  # if scheduled was balanced in previous step
        setting = True if adjustment == 1 else False  # true is home
        opp_pq = PriorityQueue()
        for opp in schedule[team]:
            if opp not in settings[team]:  # skip teams we already scheduled against
                # as a first tiebreaker, take into account the priority of the users when it
                # comes to this game: -1 if priority helps balance both, 0 if no priority,
                #                     1 if priority exists but unbalances one
                if (pref := preferences[team][opp]) is not None:
                    if pref is True and adjustment < 0:
                        # team wants home and a home game would help balance
                        priority_flag = -1
                    elif pref is False and adjustment > 0:
                        # team wants away and away would help balance
                        priority_flag = -1
                    else:
                        # whatever team wants would hurt the balance
                        priority_flag = 1
                else:
                    priority_flag = 0
                # Override the priority flag if we are ignoring preferences
                if respect_preferences is False:
                    priority_flag = 0
                opp_pq.put((priority_flag, abs(info[opp]["balance"] - balance), random.random() if seed else 0, opp))
        while balance != 0 and not opp_pq.empty():
            _, _, _, opp = opp_pq.get()
            settings[team][opp] = setting
            balance += adjustment
            # Update opp's info and position in the priority queue
            old_priority = -1 * (info[opp]["balance"] + (len(schedule[opp]) - len(settings[opp])))
            old_seed = seeds[opp]
            settings[opp][team] = not setting
            info[opp]["balance"] += (-1 * adjustment)
            new_priority = -1 * (info[opp]["balance"] + (len(schedule[opp]) - len(settings[opp])))
            new_seed = random.random() if seed else 0
            seeds[opp] = new_seed
            if abs(info[opp]["balance"]) != 1:
                # Old element will not exist if balance was previously 0
                pq.queue.remove((old_priority, old_seed, opp))
            if info[opp]["balance"] != 0:
                # Do not insert back into priority queue if balance is 0
                pq.put((new_priority, new_seed, opp))
        info[team]["balance"] = balance
        # At this point, either the balance is 0 or it is impossible to balance the schedule
        # If the balance is not 0, log the error
        # If the balance is 0, nothing more to do here
        if balance != 0:
            errors[team] = balance
    # We can now assume that either a team's balance is 0 and/or they have no more user games to decide
    # the setting for. Now, instruct on any CPU games that may be remaining
    for team in info:
        if (free_weeks := info[team]["free_weeks"]) != 3:
            num_needed = free_weeks - 3
            assert num_needed > 0
            # Branch here depending on if the team is balanced or not
            if (balance := info[team]["balance"]) == 0:
                # Split the difference between home/away to keep balance
                # If an odd number of games is needed, this will result in a half game for each,
                # representing user's choice.
                cpuGames[team]["home"] += (num_needed / 2)
                cpuGames[team]["away"] += (num_needed / 2)
            else:
                # Balance team using CPU games first, then split evenly
                # Note: not sure if it is even possible to reach this case, but better safe than sorry
                adjustment = 1 if balance < 0 else -1
                num = min(abs(balance), num_needed)
                setting = "home" if adjustment == 1 else "away"
                cpuGames[team][setting] += num
                balance += (adjustment * num)
                num_needed -= num
                if balance == 0 and num_needed > 0:
                    # Split the difference between remaining games needed, see other branch of parent if
                    cpuGames[team]["home"] += (num_needed / 2)
                    cpuGames[team]["away"] += (num_needed / 2)

    return settings, cpuGames, errors


if __name__ == "__main__":
    from pprint import pprint
    import math
    import tqdm
    import os

    # TODO: proper test cases
    requests = {
        'Clemson': {'Penn State': True},
        'Miami': {'Alabama': True, 'Arkansas': True, 'Appalachian State': True},
        'Florida State': {'Oregon': True, 'Penn State': True},
        'NC State': {'Alabama': True, 'Maryland': True, 'Baylor': True},
        'Virginia Tech': {'Baylor': True, 'Ohio State': False, 'Maryland': True, 'Missouri': True},
        'Rutgers': {'UCF': True, 'Utah': True},
        'Penn State': {'Texas A&M': True, 'Clemson': False, 'Georgia State': False, 'Florida State': False},
        'Maryland': {'LSU': True, 'Virginia Tech': False, 'NC State': False},
        'Oregon': {'Colorado': True, 'Florida State': False, 'UCF': True},
        'Ohio State': {'Baylor': True, 'UCF': True, 'Appalachian State': True, 'Virginia Tech': True},
        'Colorado': {'Texas A&M': True, 'Western Michigan': True, 'Georgia State': True, 'Oregon': False},
        'Utah': {'Georgia State': True, 'Rutgers': False, 'Western Michigan': True, 'Texas A&M': True},
        'Kansas': {'Georgia State': True, 'Missouri': True},
        'UCF': {'USF': None, 'Rutgers': False, 'Oregon': False, 'Ohio State': False},
        'Baylor': {'Virginia Tech': False, 'Texas A&M': True, 'NC State': False, 'Ohio State': False},
        'Texas A&M': {'Colorado': False, 'Penn State': False, 'Utah': False, 'Baylor': False},
        'Arkansas': {'Miami': False},
        'Alabama': {'NC State': False, 'Miami': False},
        'Missouri': {'Kansas': False, 'Virginia Tech': False},
        'LSU': {'Maryland': False},
        'Georgia State': {'Penn State': True, 'Kansas': False, 'Colorado': False, 'Utah': False},
        'Appalachian State': {'Western Michigan': False, 'Miami': False, 'Ohio State': False},
        'Western Michigan': {'Appalachian State': True, 'Colorado': False, 'Utah': False},
        'USF': {'UCF': None}
    }
    starting_schedules = {
        'Clemson': {"balance": 0, "free_weeks": SortedList([0, 1, 2, 3, 11, 12, 13])},
        'Miami': {"balance": -2, "free_weeks": SortedList([0, 1, 2, 3, 4, 5, 8])},
        'Florida State': {"balance": -2, "free_weeks": SortedList([0, 1, 2, 3, 4, 7, 13])},
        'NC State': {"balance": -2, "free_weeks": SortedList([0, 1, 2, 3, 5, 6, 9])},
        'Virginia Tech': {"balance": 0, "free_weeks": SortedList([0, 1, 2, 3, 4, 5, 7])},
        'Rutgers': {"balance": 4, "free_weeks": SortedList([0, 1, 2, 3, 4, 5, 6])},
        'Penn State': {"balance": 2, "free_weeks": SortedList([0, 1, 2, 3, 4, 5, 10])},
        'Maryland': {"balance": 0, "free_weeks": SortedList([0, 1, 2, 3, 4, 5, 6])},
        'Oregon': {"balance": -2, "free_weeks": SortedList([0, 1, 2, 3, 4, 5, 6])},
        'Ohio State': {"balance": 2, "free_weeks": SortedList([0, 1, 2, 3, 4, 5, 7])},
        'Colorado': {"balance": -2, "free_weeks": SortedList([0, 1, 2, 3, 4, 5, 6])},
        'Utah': {"balance": 2, "free_weeks": SortedList([0, 1, 2, 3, 5, 7, 8])},
        'Kansas': {"balance": -2, "free_weeks": SortedList([0, 1, 2, 3, 4, 5, 6])},
        'UCF': {"balance": -2, "free_weeks": SortedList([0, 1, 2, 3, 4, 5, 10])},
        'Baylor': {"balance": 0, "free_weeks": SortedList([0, 1, 2, 3, 4, 12, 13])},
        'Texas A&M': {"balance": -4, "free_weeks": SortedList([0, 1, 2, 3, 4, 5, 6])},
        'Arkansas': {"balance": 0, "free_weeks": SortedList([0, 1, 2, 3, 4, 8, 10, 12])},
        'Alabama': {"balance": -2, "free_weeks": SortedList([0, 1, 2, 3, 4, 5, 13])},
        'Missouri': {"balance": 0, "free_weeks": SortedList([0, 1, 2, 3, 4, 5, 6])},
        'LSU': {"balance": -2, "free_weeks": SortedList([0, 1, 2, 3, 4, 5, 6])},
        'Georgia State': {"balance": 0, "free_weeks": SortedList([0, 1, 2, 3, 4, 5, 6])},
        'Appalachian State': {"balance": 4, "free_weeks": SortedList([0, 1, 2, 3, 4, 6, 7])},
        'Western Michigan': {"balance": -4, "free_weeks": SortedList([0, 1, 2, 3, 4, 5, 10])},
        'USF': {"balance": -2, "free_weeks": SortedList([0, 1, 2, 4, 5, 6, 7])}
    }

    schedule, homeGames, cpuGames, errors = do_schedule(requests, starting_schedules, max_iter=1000)
    print()
    # separate into matchmaking errors and home/away balance errors
    schedule_errors = {}
    balance_errors = {}
    for error in errors:
        if type(error) is tuple:
            schedule_errors[error] = errors[error]
        else:
            balance_errors[error] = errors[error]

    print(f"Found schedule with {len(schedule_errors)} scheduling errors and "
          f"a balance error of {math.sqrt(sum([x ** 2 for x in errors.values()]))}")

    print("\n")

    print("Schedule:")
    pprint(schedule)
    print("\nHome games:")
    pprint(homeGames)
    print("\nCPU games:")
    pprint(cpuGames)
    if len(schedule_errors) > 0:
        print("\nSchedule errors:")
        print(schedule_errors)
    if len(balance_errors) > 0:
        print("\nBalance errors:")
        print(balance_errors)

    print()

    # Sanity check - schedules are full
    for team in starting_schedules:
        free_weeks = starting_schedules[team]["free_weeks"]
        for opp in schedule[team]:
            free_weeks.remove(schedule[team][opp])
        if len(free_weeks) - cpuGames[team]["home"] - cpuGames[team]["away"] != 3:
            print(f"Error: {team} does not have exactly 12 games scheduled")

    # schedule, schedule_errors = find_schedule(deepcopy(requests), starting_schedules)
    #
    # # pprint(result)
    #
    # # validate that games were only scheduled during free weeks
    # # also need this to call set_game_locations
    # for team in schedule:
    #     scheduled_weeks = schedule[team].values()
    #     for week in scheduled_weeks:
    #         try:
    #             starting_schedules[team]["free_weeks"].remove(week)
    #         except:
    #             f"Week {week} for {team} is not free!"
    #
    # # pprint(schedules)
    #
    # # respect_prefs = True
    # # seed = 5
    # # homeGames, cpuGames, balance_errors = set_game_locations(deepcopy(schedule), deepcopy(starting_schedules), requests,
    # #                                                          respect_preferences=respect_prefs, seed=seed)
    #
    # # max_iter starts to take minutes when at 1mil
    # max_iter = 100
    # seed_range = 100
    # curr_iter = 0
    # still_trying = True
    # best = float("inf")
    # best_settings = [None, None]
    # chosen_setting = None
    # avg = {"pref": [0, 0], "nopref": [float('inf'), 1]}
    # pbar = tqdm.tqdm(total=max_iter)
    # next_rand = list(range(0, seed_range))
    # random.shuffle(next_rand)  # randomizes order of list in-place
    # while still_trying and curr_iter < max_iter and best != 0:
    #     # try to choose the best method (pref/nopref) if at max_iter/2 iterations
    #     if curr_iter == round(max_iter / 2):
    #         pref_avg = avg["pref"][0] / avg["pref"][1]
    #         nopref_avg = avg["nopref"][0] / avg["nopref"][1]
    #         os.system("clear")
    #         if math.isclose(pref_avg, nopref_avg, rel_tol=0.05):
    #             print(f"Not choosing to respect preferences or not, "
    #                   f"diff {pref_avg} ({avg['pref'][1]} pref obs.) vs {nopref_avg} ({avg['nopref'][1]} nopref obs.)")
    #         elif pref_avg < nopref_avg:
    #             print(f"Choosing to repsect preferences, "
    #                   f"diff {pref_avg} ({avg['pref'][1]} obs.) vs {nopref_avg} ({avg['nopref'][1]} obs.)")
    #             chosen_setting = True
    #         elif nopref_avg < pref_avg:
    #             print(f"Choosing not to repsect preferences, "
    #                   f"diff {nopref_avg} ({avg['nopref'][1]} obs.) vs {pref_avg} ({avg['pref'][1]} obs.)")
    #             chosen_setting = False
    #
    #     respect_prefs = random.choice([True]) if chosen_setting is None else chosen_setting
    #     seed = next_rand[curr_iter]
    #     homeGames, cpuGames, balance_errors = set_game_locations(deepcopy(schedule), deepcopy(starting_schedules),
    #                                                              requests,
    #                                                              respect_preferences=respect_prefs, seed=seed)
    #     error = math.sqrt(sum([x ** 2 for x in balance_errors.values()]))
    #     if error < best:
    #         best = error
    #         best_settings = [respect_prefs, seed]
    #     pref = "pref" if respect_prefs else "nopref"
    #     avg[pref][0] += error
    #     avg[pref][1] += 1
    #     curr_iter += 1
    #     pbar.update(1)
    #
    # pbar.close()
    # respect_prefs = best_settings[0]
    # seed = best_settings[1]
    #
    # if best == 0:
    #     print(f"Exited early with optimal solution at {curr_iter} iterations")
    #
    # # Check to make sure a team has a home/away for every user game
    # print(f"Issue teams: {', '.join([t for t in schedule if len(schedule[t]) != len(homeGames[t])])}")
    # # Check that a team is fully scheduled (only 3 free weeks after considering CPU games)
    # for team in cpuGames:
    #     num_cpu_games = sum(cpuGames[team].values())
    #     if (amt := len(starting_schedules[team]["free_weeks"]) - num_cpu_games) != 3:
    #         print(f"{team} has {amt} bye weeks (should have 3)")
    # # Print error of chosen schedule
    # print("Errors:")
    # error = math.sqrt(sum([x**2 for x in balance_errors.values()]))
    # print(f"repsect_preferences={respect_prefs}, seed={seed}, error={error}")
    # print(balance_errors)

