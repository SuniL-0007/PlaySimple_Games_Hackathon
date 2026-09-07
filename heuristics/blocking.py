import itertools


def nearest_exit(level, block, anchor):
    ax, ay = level.anchor_position(anchor)
    best = -1
    best_cost = None
    for exit_anchor in level.exit_anchors[block]:
        ex, ey = level.anchor_position(exit_anchor)
        cost = ((ax != ex) + (ay != ey), abs(ax - ex) + abs(ay - ey))
        if best_cost is None or cost < best_cost:
            best, best_cost = exit_anchor, cost
    return best


def corridor_table(level):
    return tuple(
        (*(corridors(level, block, anchor) for anchor in range(level.cells)), (0, 0))
        for block in range(len(level.blocks))
    )


def corridors(level, block, anchor):
    exit_anchor = nearest_exit(level, block, anchor)
    if exit_anchor < 0 or exit_anchor == anchor:
        return (0, 0)
    ax, ay = level.anchor_position(anchor)
    ex, ey = level.anchor_position(exit_anchor)
    corner_first_horizontal = level.anchor_index(ex, ay)
    corner_first_vertical = level.anchor_index(ax, ey)
    own = level.masks[block][anchor]
    return (
        swept_cells(level, block, (anchor, corner_first_horizontal, exit_anchor)) & ~own,
        swept_cells(level, block, (anchor, corner_first_vertical, exit_anchor)) & ~own,
    )


def swept_cells(level, block, waypoints):
    swept = 0
    for start, end in itertools.pairwise(waypoints):
        swept |= swept_along_line(level, block, start, end)
    return swept


def swept_along_line(level, block, start, end):
    sx, sy = level.anchor_position(start)
    ex, ey = level.anchor_position(end)
    xs = range(min(sx, ex), max(sx, ex) + 1)
    ys = range(min(sy, ey), max(sy, ey) + 1)
    swept = 0
    for y in ys:
        for x in xs:
            swept |= level.masks[block][level.anchor_index(x, y)]
    return swept
