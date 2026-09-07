from typing import NamedTuple

SOLVED = "SOLVED"
UNSOLVABLE = "UNSOLVABLE"
TIMEOUT = "TIMEOUT"

MAX_STORED_STATES = 2_500_000
DEADLINE_CHECK_INTERVAL = 1024
GENERATED_CHECK_INTERVAL = 256


class DeadlineExceeded(Exception):
    pass


class SearchResult(NamedTuple):
    status: str
    moves: tuple
    expanded: int
    generated: int
    stored: int
    optimal: bool = True
    improvements: tuple = ()


def reconstruct_moves(parents, moves, node):
    path = []
    while node > 0:
        path.append(moves[node])
        node = parents[node]
    path.reverse()
    return tuple(path)
