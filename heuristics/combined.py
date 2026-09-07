from heuristics.blocking import corridor_table
from heuristics.dependency import dependency_penalty

DEPENDENCY_WEIGHT = 1
FROZEN_PENALTY = 1


def frozen_count(level, state):
    exits = state.exit_mask.bit_count()
    return sum(
        1
        for block in level.pending_blocks
        if level.blocks[block].ice > exits and not state.exit_mask >> block & 1
    )


def guide(level):
    corridors = corridor_table(level)

    def estimate(state):
        dependency = DEPENDENCY_WEIGHT * dependency_penalty(level, corridors, state)
        return dependency + FROZEN_PENALTY * frozen_count(level, state)

    return estimate
