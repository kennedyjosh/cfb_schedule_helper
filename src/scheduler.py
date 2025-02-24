from copy import deepcopy
from queue import PriorityQueue
import random
from sortedcontainers import SortedList


def _matchup(t1, t2):
     return (min(t1, t2), max(t1, t2))


# TODO: make sure teams with no requests are removed from both inputs

# This should be the only function called from here
def schedule(requests, schedule_info):
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
    schedule, errors = find_schedule(deepcopy(requests), schedule_info)



def find_schedule(requests, current_schedules):
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
            pq.put((priority, matchup))
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
        _, matchup = pq.get()
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
                    pq.queue.remove((priority_dict[other_matchup], other_matchup))
                    priority_dict[other_matchup] = new_priority
                    pq.put((new_priority, other_matchup))

    return schedule, errors




if __name__ == "__main__":
    from pprint import pprint

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
    schedules = {
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

    result, errors = find_schedule(deepcopy(requests), schedules)

    pprint(result)

    # validate that games were only scheduled during free weeks
    for team in result:
        scheduled_weeks = result[team].values()
        for week in scheduled_weeks:
            try:
                schedules[team]["free_weeks"].remove(week)
            except:
                f"Week {week} for {team} is not free!"

    pprint(schedules)

