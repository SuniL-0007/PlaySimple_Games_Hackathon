from collections import deque

UNREACHABLE = float("inf")


def slide_distances(level, block):
    distances = [UNREACHABLE] * (level.cells + 1)
    distances[level.exited_anchor] = 0
    frontier = deque()
    for exit_anchor in level.exit_anchors[block]:
        distances[exit_anchor] = 0
        frontier.append(exit_anchor)
    while frontier:
        anchor = frontier.popleft()
        for direction in level.allowed_directions[block]:
            for neighbour in wall_free_slides(level, block, anchor, direction):
                if distances[neighbour] == UNREACHABLE:
                    distances[neighbour] = distances[anchor] + 1
                    frontier.append(neighbour)
    return tuple(distances)


def wall_free_slides(level, block, anchor, direction):
    step = level.steps[block][direction]
    masks = level.masks[block]
    anchor = step[anchor]
    while anchor >= 0 and not masks[anchor] & level.walls:
        yield anchor
        anchor = step[anchor]


def distance_table(level):
    return tuple(slide_distances(level, block) for block in range(len(level.blocks)))


def distance(level, table, state):
    total = 0
    for block in level.pending_blocks:
        total += table[block][state.anchors[block]]
    return total


def contributions(level, table):
    pending = set(level.pending_blocks)
    settled = (0,) * (level.cells + 1)
    return tuple(table[block] if block in pending else settled for block in range(len(level.blocks)))
