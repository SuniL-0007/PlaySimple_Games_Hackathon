from heuristics.combined import guide
from search.astar import BestFirstSearch
from search.complete import admissible_heuristic

WEIGHT = 3.0


def solve(level, deadline):
    estimate, shares = admissible_heuristic(level)
    return BestFirstSearch(level, deadline, estimate, shares, WEIGHT, guide(level), WEIGHT).run()
