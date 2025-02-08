import re
import string

STANDARDIZED_NAMES = [
    "Air Force",
    "Akron",
    "Alabama",
    "Appalachian State",
    "Arizona",
    "Arizona State",
    "Arkansas",
    "Arkansas State",
    "Army",
    "Auburn",
    "Ball State",
    "Baylor",
    "Boise State",
    "Boston College",
    "Bowling Green",
    "Buffalo",
    "BYU",
    "California",
    "Central Michigan",
    "Charlotte",
    "Cincinnati",
    "Clemson",
    "Coastal Carolina",
    "Colorado",
    "Colorado State",
    "Duke",
    "East Carolina",
    "Eastern Michigan",
    "Florida",
    "Florida Atlantic",
    "Florida International",
    "Florida State",
    "Fresno State",
    "Georgia",
    "Georgia Southern",
    "Georgia State",
    "Georgia Tech",
    "Hawaii",
    "Houston",
    "Illinois",
    "Indiana",
    "Iowa",
    "Iowa State",
    "Jacksonville State",
    "James Madison",
    "Kansas",
    "Kansas State",
    "Kennesaw State",
    "Kent State",
    "Kentucky",
    "Liberty",
    "Louisiana",
    "Louisiana Tech",
    "Louisville",
    "LSU",
    "Marshall",
    "Maryland",
    "Memphis",
    "Miami",
    "Miami University",
    "Michigan",
    "Michigan State",
    "Middle Tennessee St",
    "Minnesota",
    "Mississippi State",
    "Missouri",
    "Navy",
    "NC State",
    "Nebraska",
    "Nevada",
    "New Mexico",
    "New Mexico State",
    "North Carolina",
    "North Texas",
    "Northern Illinois",
    "Northwestern",
    "Notre Dame",
    "Ohio",
    "Ohio State",
    "Oklahoma",
    "Oklahoma State",
    "Old Dominion",
    "Ole Miss",
    "Oregon",
    "Oregon State",
    "Penn State",
    "Pittsburgh",
    "Purdue",
    "Rice",
    "Rutgers",
    "Sam Houston",
    "San Diego State",
    "San Jose State",
    "SMU",
    "South Alabama",
    "South Carolina",
    "Southern Mississippi",
    "Stanford",
    "Syracuse",
    "TCU",
    "Temple",
    "Tennessee",
    "Texas",
    "Texas A&M",
    "Texas State",
    "Texas Tech",
    "Toledo",
    "Troy",
    "Tulane",
    "Tulsa",
    "UAB",
    "UCF",
    "UCLA",
    "UConn",
    "UL Monroe",
    "UMass",
    "UNLV",
    "USC",
    "USF",
    "Utah",
    "Utah State",
    "UTEP",
    "UTSA",
    "Vanderbilt",
    "Virginia",
    "Virginia Tech",
    "Wake Forest",
    "Washington",
    "Washington State",
    "West Virginia",
    "Western Kentucky",
    "Western Michigan",
    "Wisconsin",
    "Wyoming"
]

STANDARDIZED_NAMES_LOWERCASE = list(map(lambda x: x.lower(), STANDARDIZED_NAMES))


def standardize(team):
    """
    Attempt to standardize a team name.
    Will throw a ValueError if the name cannot be standardized
    """
    # Simple case, team name is already standardized
    if team in STANDARDIZED_NAMES:
        return team

    # Team name is standardized but capitalization is wrong
    og_team = team
    team = team.lower().strip()
    if (index := _binary_search(team)) != -1:
        return STANDARDIZED_NAMES[index]

    # Try some common substitutions
    # TODO: add some more cases here, make this more robust
    # Remove any punctuation or non-alpha symbols
    team = re.compile("[^a-zA-Z ]").sub("", team)
    team.translate(str.maketrans('', '', string.punctuation))
    if (index := _binary_search(team)) != -1:
        return STANDARDIZED_NAMES[index]

    # 'app' -> 'appalachian'
    team = re.sub("^app ", "appalachian ", team)
    # 'st' -> 'state'
    team = re.sub(" st$", " state", team)
    # last try to match the name
    if (index := _binary_search(team)) != -1:
        return STANDARDIZED_NAMES[index]

    raise ValueError(f"Team could not be standardized: {og_team}")


def _binary_search(target: str) -> int:
    """
    Perform a binary search on the sorted list STANDARDIZED_NAMES.
    Returns the index of the target element if found, otherwise -1.
    """
    left, right = 0, len(STANDARDIZED_NAMES_LOWERCASE) - 1

    while left <= right:
        mid = (left + right) // 2
        mid_value = STANDARDIZED_NAMES_LOWERCASE[mid]

        if mid_value == target:
            return mid
        elif mid_value < target:
            left = mid + 1
        else:
            right = mid - 1

    return -1


if __name__ == "__main__":
    ## TODO need formal tests for this file
    assert standardize("Florida St") == "Florida State"
    assert standardize("App State") == "Appalachian State"
    assert standardize("Oregon+") == "Oregon"
