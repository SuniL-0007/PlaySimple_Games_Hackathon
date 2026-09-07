from heuristics.distance import contributions, distance, distance_table
from search.astar import BestFirstSearch

ADMISSIBLE_WEIGHT = 1


def admissible_heuristic(level):
    table = distance_table(level)

    def estimate(state):
        return distance(level, table, state)

    return estimate, contributions(level, table)


def solve(level, deadline):
    estimate, shares = admissible_heuristic(level)
    return BestFirstSearch(level, deadline, estimate, shares, ADMISSIBLE_WEIGHT).run()
