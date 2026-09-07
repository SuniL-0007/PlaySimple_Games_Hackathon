from typing import NamedTuple


class State(NamedTuple):
    anchors: bytes
    exit_mask: int


def initial_state(level):
    return State(bytes(level.anchor_index(*block.origin) for block in level.blocks), 0)


def occupancy(level, anchors):
    occupied = 0
    for masks, anchor in zip(level.masks, anchors, strict=True):
        occupied |= masks[anchor]
    return occupied


def canonical_key(level, anchors):
    slices = level.sorted_slices
    if not slices:
        return bytes(anchors)
    key = bytearray(anchors)
    for start, end in slices:
        if end - start == 2:
            first, second = key[start], key[start + 1]
            if first > second:
                key[start], key[start + 1] = second, first
        else:
            key[start:end] = sorted(key[start:end])
    return bytes(key)
