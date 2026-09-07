from dataclasses import dataclass

TOP = "top"
BOTTOM = "bottom"
LEFT = "left"
RIGHT = "right"
SIDES = (TOP, BOTTOM, LEFT, RIGHT)

HORIZONTAL = "h"
VERTICAL = "v"

RIGHTWARD, LEFTWARD, DOWNWARD, UPWARD = range(4)
DIRECTION_DELTAS = ((1, 0), (-1, 0), (0, 1), (0, -1))
HORIZONTAL_DIRECTIONS = (RIGHTWARD, LEFTWARD)
VERTICAL_DIRECTIONS = (DOWNWARD, UPWARD)
SIDE_AXIS = {TOP: VERTICAL, BOTTOM: VERTICAL, LEFT: HORIZONTAL, RIGHT: HORIZONTAL}


@dataclass(frozen=True)
class Block:
    id: str
    color: str
    cells: tuple
    origin: tuple
    ice: int = 0
    axis: str | None = None

    @property
    def width(self):
        return 1 + max(dx for dx, _ in self.cells)

    @property
    def height(self):
        return 1 + max(dy for _, dy in self.cells)

    @property
    def tag_offset(self):
        return min(self.cells, key=lambda cell: (cell[1], cell[0]))

    @property
    def interchangeability(self):
        return (self.color, self.cells, self.ice, self.axis)


@dataclass(frozen=True)
class Gate:
    id: str
    color: str
    side: str
    start: int
    length: int


@dataclass(frozen=True)
class Level:
    width: int
    height: int
    walls: int
    blocks: tuple
    gates: tuple
    masks: tuple
    steps: tuple
    allowed_directions: tuple
    exit_shadows: tuple
    exit_anchors: tuple
    ice_thresholds: tuple
    pending_blocks: tuple
    pending_mask: int
    groups: tuple
    sorted_slices: tuple
    group_spans: tuple

    @property
    def cells(self):
        return self.width * self.height

    @property
    def exited_anchor(self):
        return self.cells

    def anchor_index(self, x, y):
        return y * self.width + x

    def anchor_position(self, anchor):
        return anchor % self.width, anchor // self.width

    def block_index(self, block_id):
        for index, block in enumerate(self.blocks):
            if block.id == block_id:
                return index
        raise KeyError(f"no block with id {block_id!r}")


def build_level(width, height, walls, blocks, gates):
    blocks = grouped_by_interchangeability(blocks)
    gates = tuple(gates)
    groups = interchangeable_groups(blocks)
    gate_colors = {gate.color for gate in gates}
    pending = tuple(i for i, block in enumerate(blocks) if block.color in gate_colors)
    shadows = [exit_shadows(width, height, block, gates) for block in blocks]
    cells = width * height
    return Level(
        width=width,
        height=height,
        walls=walls,
        blocks=blocks,
        gates=gates,
        masks=tuple(shape_masks(width, height, block) for block in blocks),
        steps=tuple(step_tables(width, height, block) for block in blocks),
        allowed_directions=tuple(allowed_directions(block) for block in blocks),
        exit_shadows=tuple(
            tuple(by_anchor.get(anchor) for anchor in range(cells + 1)) for by_anchor in shadows
        ),
        exit_anchors=tuple(tuple(sorted(by_anchor)) for by_anchor in shadows),
        ice_thresholds=tuple(block.ice for block in blocks),
        pending_blocks=pending,
        pending_mask=sum(1 << i for i in pending),
        groups=groups,
        sorted_slices=tuple((group[0], group[-1] + 1) for group in groups if len(group) > 1),
        group_spans=group_spans(blocks, groups),
    )


def group_spans(blocks, groups):
    spans = [None] * len(blocks)
    for group in groups:
        if len(group) > 1:
            for member in group:
                spans[member] = (group[0], group[-1] + 1)
    return tuple(spans)


def grouped_by_interchangeability(blocks):
    first_seen = {}
    for index, block in enumerate(blocks):
        first_seen.setdefault(block.interchangeability, index)
    return tuple(sorted(blocks, key=lambda block: first_seen[block.interchangeability]))


def is_valid_anchor(width, height, block, ax, ay):
    return 0 <= ax <= width - block.width and 0 <= ay <= height - block.height


def cells_mask(width, cells):
    mask = 0
    for x, y in cells:
        mask |= 1 << (y * width + x)
    return mask


def shape_mask(width, block, ax, ay):
    return cells_mask(width, ((ax + dx, ay + dy) for dx, dy in block.cells))


def shape_masks(width, height, block):
    table = []
    for anchor in range(width * height):
        ax, ay = anchor % width, anchor // width
        valid = is_valid_anchor(width, height, block, ax, ay)
        table.append(shape_mask(width, block, ax, ay) if valid else 0)
    table.append(0)
    return tuple(table)


def step_tables(width, height, block):
    return tuple(step_table(width, height, block, delta) for delta in DIRECTION_DELTAS)


def step_table(width, height, block, delta):
    dx, dy = delta
    table = []
    for anchor in range(width * height):
        ax, ay = anchor % width + dx, anchor // width + dy
        origin_valid = is_valid_anchor(width, height, block, ax - dx, ay - dy)
        reachable = origin_valid and is_valid_anchor(width, height, block, ax, ay)
        table.append(ay * width + ax if reachable else -1)
    table.append(-1)
    return tuple(table)


def allowed_directions(block):
    if block.axis == HORIZONTAL:
        return HORIZONTAL_DIRECTIONS
    if block.axis == VERTICAL:
        return VERTICAL_DIRECTIONS
    return HORIZONTAL_DIRECTIONS + VERTICAL_DIRECTIONS


def exit_shadows(width, height, block, gates):
    shadows = {}
    for gate in gates:
        if gate.color != block.color or block.axis not in (None, SIDE_AXIS[gate.side]):
            continue
        for ax, ay in gate_anchors(width, height, block, gate):
            anchor = ay * width + ax
            shadow = shadow_mask(width, height, block, gate.side, ax, ay)
            shadows.setdefault(anchor, []).append(shadow)
    return {anchor: tuple(masks) for anchor, masks in shadows.items()}


def gate_anchors(width, height, block, gate):
    span = range(gate.start, gate.start + gate.length - block_extent(block, gate.side) + 1)
    if gate.side == TOP:
        return [(x, 0) for x in span]
    if gate.side == BOTTOM:
        return [(x, height - block.height) for x in span]
    if gate.side == LEFT:
        return [(0, y) for y in span]
    return [(width - block.width, y) for y in span]


def block_extent(block, side):
    return block.width if side in (TOP, BOTTOM) else block.height


def shadow_mask(width, height, block, side, ax, ay):
    cells = []
    if side in (TOP, BOTTOM):
        for dx in range(block.width):
            column = [dy for cx, dy in block.cells if cx == dx]
            rows = range(0, ay + min(column)) if side == TOP else range(ay + max(column) + 1, height)
            cells.extend((ax + dx, y) for y in rows)
    else:
        for dy in range(block.height):
            row = [dx for dx, cy in block.cells if cy == dy]
            columns = range(0, ax + min(row)) if side == LEFT else range(ax + max(row) + 1, width)
            cells.extend((x, ay + dy) for x in columns)
    return cells_mask(width, cells)


def interchangeable_groups(blocks):
    groups = {}
    for index, block in enumerate(blocks):
        groups.setdefault(block.interchangeability, []).append(index)
    return tuple(tuple(members) for members in groups.values())
