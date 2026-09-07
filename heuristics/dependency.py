BLOCKER_CAP = 4


def live_masks(level, anchors):
    return [masks[anchor] for masks, anchor in zip(level.masks, anchors, strict=True)]


def blockers_of(level, corridors, masks, block, anchor):
    candidates = []
    for corridor in corridors[block][anchor]:
        if not corridor:
            continue
        found = [other for other, mask in enumerate(masks) if other != block and mask & corridor]
        candidates.append(found)
    if not candidates:
        return []
    return min(candidates, key=len)


def dependency_penalty(level, corridors, state):
    masks = live_masks(level, state.anchors)
    blockers = {}
    for block in level.pending_blocks:
        if not state.exit_mask >> block & 1:
            blockers[block] = blockers_of(level, corridors, masks, block, state.anchors[block])
    penalty = 0
    for direct in blockers.values():
        chained = sum(min(len(blockers.get(other, ())), BLOCKER_CAP) for other in direct)
        penalty += min(len(direct), BLOCKER_CAP) + chained
    return penalty
