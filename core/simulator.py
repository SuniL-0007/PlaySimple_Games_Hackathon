from core.state import State, occupancy


def apply_move(level, state, move):
    block, anchor = move
    anchors = bytearray(state.anchors)
    anchors[block] = anchor
    candidates = exit_candidates(level, anchors)
    exit_mask = release_exiting_blocks(level, anchors, state.exit_mask, candidates)
    return State(bytes(anchors), exit_mask)


def exit_candidates(level, anchors):
    exit_shadows = level.exit_shadows
    return [block for block in level.pending_blocks if exit_shadows[block][anchors[block]] is not None]


def release_exiting_blocks(level, anchors, exit_mask, candidates):
    exit_shadows = level.exit_shadows
    ice_thresholds = level.ice_thresholds
    masks = level.masks
    exited = level.exited_anchor
    exits = exit_mask.bit_count()
    occupied = None
    released = True
    while released:
        released = False
        for block in candidates:
            anchor = anchors[block]
            shadows = exit_shadows[block][anchor]
            if shadows is None or ice_thresholds[block] > exits:
                continue
            if occupied is None:
                occupied = occupancy(level, anchors) | level.walls
            obstacles = occupied ^ masks[block][anchor]
            for shadow in shadows:
                if not shadow & obstacles:
                    anchors[block] = exited
                    exit_mask |= 1 << block
                    exits += 1
                    occupied = obstacles
                    released = True
                    break
    return exit_mask


def is_goal(level, state):
    return level.pending_mask & ~state.exit_mask == 0
