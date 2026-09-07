from heuristics.combined import guide
from search.astar import BestFirstSearch
from search.complete import admissible_heuristic

SCHEDULE = ((3.0, 3.0), (2.0, 2.0), (1.5, 1.5), (1.0, 0.0))


def solve(level, deadline):
    estimate, shares = admissible_heuristic(level)
    (weight, guide_weight), *refinements = SCHEDULE
    search = BestFirstSearch(level, deadline, estimate, shares, weight, guide(level), guide_weight)
    return search.run(refinements)
