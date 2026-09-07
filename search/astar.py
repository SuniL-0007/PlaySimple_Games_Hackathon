import heapq
import math
import time

from core.moves import legal_moves
from core.simulator import exit_candidates, is_goal, release_exiting_blocks
from core.state import State, canonical_key, initial_state
from search.result import (
    DEADLINE_CHECK_INTERVAL,
    GENERATED_CHECK_INTERVAL,
    MAX_STORED_STATES,
    SOLVED,
    TIMEOUT,
    UNSOLVABLE,
    DeadlineExceeded,
    SearchResult,
    reconstruct_moves,
)


class BestFirstSearch:
    def __init__(self, level, deadline, estimate, contributions, weight, guide=None, guide_weight=0.0):
        self.level = level
        self.deadline = deadline
        self.estimate = estimate
        self.contributions = contributions
        self.weight = weight
        self.guide = guide
        self.guide_weight = guide_weight
        self.parents = [-1]
        self.moves = [None]
        self.best_depth = {}
        self.open = []
        self.expanded = 0
        self.generated = 0
        self.bound = math.inf
        self.incumbent = -1
        self.improvements = []
        self.started = 0.0

    def run(self, refinements=()):
        self.started = time.monotonic()
        start = initial_state(self.level)
        start_key = canonical_key(self.level, start.anchors)
        if not self.push(0, 0, start, start_key, None):
            return self.finish(UNSOLVABLE, True)
        phases = iter(refinements)
        level = self.level
        best_depth = self.best_depth
        open_states = self.open
        while open_states:
            _, negated_depth, node, state, key, h_adm, _ = heapq.heappop(open_states)
            depth = -negated_depth
            if depth > best_depth[key] or depth + h_adm >= self.bound:
                continue
            if is_goal(level, state):
                self.improve(node, depth)
                phase = next(phases, None)
                if self.is_exact() or phase is None:
                    return self.finish(SOLVED, self.is_exact())
                if time.monotonic() > self.deadline:
                    return self.finish_interrupted()
                self.retarget(*phase)
                continue
            self.expanded += 1
            if self.expanded % DEADLINE_CHECK_INTERVAL == 0 and time.monotonic() > self.deadline:
                return self.finish_interrupted()
            try:
                self.expand(node, depth, state, key, h_adm)
            except DeadlineExceeded:
                return self.finish_interrupted()
            if len(self.parents) > MAX_STORED_STATES:
                return self.finish_interrupted()
        if self.incumbent >= 0:
            return self.finish(SOLVED, True)
        return self.finish(UNSOLVABLE, True)

    def is_exact(self):
        return self.weight == 1.0 and self.guide_weight == 0.0

    def improve(self, node, depth):
        self.incumbent = node
        self.bound = depth
        elapsed = time.monotonic() - self.started
        self.improvements.append((self.weight, self.guide_weight, depth, self.expanded, elapsed))

    def retarget(self, weight, guide_weight):
        needs_guide = guide_weight > 0 and self.guide_weight == 0
        self.weight = weight
        self.guide_weight = guide_weight
        best_depth = self.best_depth
        rebuilt = []
        for _, negated_depth, node, state, key, h_adm, h_guide in self.open:
            depth = -negated_depth
            if best_depth[key] != depth or depth + h_adm >= self.bound:
                continue
            if needs_guide:
                h_guide = self.guide(state)
            priority = self.priority(depth, h_adm, h_guide)
            rebuilt.append((priority, negated_depth, node, state, key, h_adm, h_guide))
        self.open[:] = rebuilt
        heapq.heapify(self.open)

    def expand(self, node, depth, state, parent_key, h_adm):
        level = self.level
        exit_shadows = level.exit_shadows
        group_spans = level.group_spans
        contributions = self.contributions
        seen_depth = self.best_depth.get
        parents = self.parents
        recorded = self.moves
        anchors = state.anchors
        exit_mask = state.exit_mask
        candidates = exit_candidates(level, anchors)
        placements = bytearray(anchors)
        key_buffer = bytearray(parent_key)
        child_depth = depth + 1
        generated = self.generated
        sliding = -1
        bystanders = candidates
        span = shares = None
        paired = False
        start = end = home = 0
        cascaded = False
        for block, stop in legal_moves(level, state):
            if cascaded:
                placements[:] = anchors
                cascaded = False
            if block != sliding:
                if sliding >= 0:
                    placements[sliding] = anchors[sliding]
                    key_buffer[:] = parent_key
                sliding = block
                bystanders = [other for other in candidates if other != block]
                span = group_spans[block]
                paired = span is not None and span[1] - span[0] == 2
                if span is not None:
                    start, end = span
                if contributions is not None:
                    shares = contributions[block]
                    home = shares[anchors[block]]
            generated += 1
            if generated % GENERATED_CHECK_INTERVAL == 0 and time.monotonic() > self.deadline:
                self.generated = generated
                raise DeadlineExceeded()
            placements[block] = stop
            live = [*bystanders, block] if exit_shadows[block][stop] is not None else bystanders
            child_mask = release_exiting_blocks(level, placements, exit_mask, live) if live else exit_mask
            if child_mask != exit_mask:
                cascaded = True
                key = canonical_key(level, placements)
                child_estimate = None
            else:
                if span is None:
                    key_buffer[block] = stop
                elif paired:
                    first, second = placements[start], placements[start + 1]
                    if first > second:
                        first, second = second, first
                    key_buffer[start], key_buffer[start + 1] = first, second
                else:
                    key_buffer[start:end] = sorted(placements[start:end])
                key = bytes(key_buffer)
                child_estimate = None if shares is None else h_adm + shares[stop] - home
            known = seen_depth(key)
            if known is not None and known <= child_depth:
                continue
            parents.append(node)
            recorded.append((block, stop))
            child = State(bytes(placements), child_mask)
            self.push(len(parents) - 1, child_depth, child, key, child_estimate)
        self.generated = generated

    def push(self, node, depth, state, key, h_adm):
        if h_adm is None:
            h_adm = self.estimate(state)
        if h_adm == math.inf:
            return False
        self.best_depth[key] = depth
        if depth + h_adm >= self.bound:
            return False
        h_guide = self.guide(state) if self.guide_weight > 0 else 0.0
        entry = (self.priority(depth, h_adm, h_guide), -depth, node, state, key, h_adm, h_guide)
        heapq.heappush(self.open, entry)
        return True

    def priority(self, depth, h_adm, h_guide):
        return depth + self.weight * h_adm + self.guide_weight * h_guide

    def finish_interrupted(self):
        if self.incumbent >= 0:
            return self.finish(SOLVED, False)
        return self.finish(TIMEOUT, False)

    def finish(self, status, optimal):
        moves = reconstruct_moves(self.parents, self.moves, self.incumbent) if status == SOLVED else ()
        return SearchResult(
            status,
            moves,
            self.expanded,
            self.generated,
            len(self.best_depth),
            optimal,
            tuple(self.improvements),
        )
