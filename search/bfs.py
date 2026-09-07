import time
from collections import deque

from core.moves import legal_moves
from core.simulator import apply_move, is_goal
from core.state import canonical_key, initial_state
from search.result import (
    DEADLINE_CHECK_INTERVAL,
    MAX_STORED_STATES,
    SOLVED,
    TIMEOUT,
    UNSOLVABLE,
    SearchResult,
    reconstruct_moves,
)


class BreadthFirstSearch:
    def __init__(self, level, deadline):
        self.level = level
        self.deadline = deadline
        self.parents = [-1]
        self.moves = [None]
        self.closed = set()
        self.frontier = deque()
        self.expanded = 0
        self.generated = 0

    def run(self):
        start = initial_state(self.level)
        if is_goal(self.level, start):
            return self.finish(SOLVED, 0)
        self.closed.add(canonical_key(self.level, start.anchors))
        self.frontier.append((0, start))
        while self.frontier:
            node, state = self.frontier.popleft()
            self.expanded += 1
            if self.expanded % DEADLINE_CHECK_INTERVAL == 0 and time.monotonic() > self.deadline:
                return self.finish(TIMEOUT)
            goal = self.expand(node, state)
            if goal >= 0:
                return self.finish(SOLVED, goal)
            if len(self.parents) > MAX_STORED_STATES:
                return self.finish(TIMEOUT)
        return self.finish(UNSOLVABLE)

    def expand(self, node, state):
        for move in legal_moves(self.level, state):
            self.generated += 1
            child = apply_move(self.level, state, move)
            key = canonical_key(self.level, child.anchors)
            if key in self.closed:
                continue
            self.closed.add(key)
            self.parents.append(node)
            self.moves.append(move)
            child_node = len(self.parents) - 1
            if is_goal(self.level, child):
                return child_node
            self.frontier.append((child_node, child))
        return -1

    def finish(self, status, goal=-1):
        moves = reconstruct_moves(self.parents, self.moves, goal) if status == SOLVED else ()
        return SearchResult(status, moves, self.expanded, self.generated, len(self.closed))


def solve(level, deadline):
    return BreadthFirstSearch(level, deadline).run()
