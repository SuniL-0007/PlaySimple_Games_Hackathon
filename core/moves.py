from core.state import occupancy


def legal_moves(level, state):
    anchors = state.anchors
    occupied = occupancy(level, anchors) | level.walls
    exit_mask = state.exit_mask
    exits = exit_mask.bit_count()
    masks_by_block = level.masks
    steps_by_block = level.steps
    directions_by_block = level.allowed_directions
    ice_thresholds = level.ice_thresholds
    for block, anchor in enumerate(anchors):
        if exit_mask >> block & 1 or ice_thresholds[block] > exits:
            continue
        masks = masks_by_block[block]
        steps = steps_by_block[block]
        blocked = occupied ^ masks[anchor]
        for direction in directions_by_block[block]:
            step = steps[direction]
            stop = step[anchor]
            while stop >= 0 and not masks[stop] & blocked:
                yield block, stop
                stop = step[stop]
