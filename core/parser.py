from core.model import BOTTOM, HORIZONTAL, LEFT, RIGHT, TOP, VERTICAL, Block, Gate, build_level, cells_mask

EMPTY = "."
WALL = "#"
GRID_NAMES = ("COLOR:", "ID:", "MODIFIERS:")


class LevelFormatError(ValueError):
    pass


def parse_level(text):
    lines = text.splitlines()
    width = header_value(lines, "w")
    height = header_value(lines, "h")
    color, ids, modifiers = (read_grid(lines, name, height + 2, width + 2) for name in GRID_NAMES)
    walls = wall_cells(color, width, height)
    blocks = parse_blocks(color, ids, modifiers, width, height)
    gates = parse_gates(color, ids, width, height)
    return build_level(width, height, cells_mask(width, walls), blocks, gates)


def header_value(lines, key):
    prefix = f"{key}="
    for number, line in enumerate(lines, 1):
        if line.strip().startswith(prefix):
            value = line.strip()[len(prefix):]
            if not value.isdigit() or int(value) == 0:
                raise LevelFormatError(f"line {number}: {key} must be a positive integer, got {value!r}")
            return int(value)
    raise LevelFormatError(f"missing header line {prefix}<N>")


def read_grid(lines, name, rows, columns):
    start = grid_start(lines, name)
    grid = []
    number = start
    while len(grid) < rows:
        if number >= len(lines):
            raise LevelFormatError(f"{name} expected {rows} rows, found {len(grid)}")
        tokens = lines[number].split()
        number += 1
        if not tokens:
            continue
        if len(tokens) != columns:
            found = len(tokens)
            raise LevelFormatError(f"line {number}: {name} row expected {columns} tokens, found {found}")
        grid.append(tokens)
    return grid


def grid_start(lines, name):
    for number, line in enumerate(lines):
        if line.strip() == name:
            return number + 1
    raise LevelFormatError(f"missing section {name}")


def interior_cells(width, height):
    return ((x, y) for y in range(height) for x in range(width))


def wall_cells(color, width, height):
    return [(x, y) for x, y in interior_cells(width, height) if color[y + 1][x + 1] == WALL]


def parse_blocks(color, ids, modifiers, width, height):
    cells_by_id = {}
    for x, y in interior_cells(width, height):
        token = ids[y + 1][x + 1]
        if token in (EMPTY, WALL):
            continue
        if color[y + 1][x + 1] == WALL:
            raise LevelFormatError(f"block {token!r} at ({x}, {y}) overlaps a wall")
        cells_by_id.setdefault(token, []).append((x, y))
    return [build_block(block_id, cells, color, modifiers) for block_id, cells in cells_by_id.items()]


def build_block(block_id, cells, color, modifiers):
    origin_x = min(x for x, _ in cells)
    origin_y = min(y for _, y in cells)
    colors = {color[y + 1][x + 1] for x, y in cells}
    if len(colors) != 1 or EMPTY in colors:
        raise LevelFormatError(f"block {block_id!r} has inconsistent colors {sorted(colors)}")
    tags = {modifiers[y + 1][x + 1] for x, y in cells} - {EMPTY}
    if len(tags) > 1:
        raise LevelFormatError(f"block {block_id!r} has conflicting modifiers {sorted(tags)}")
    ice, axis = parse_modifier(block_id, tags.pop() if tags else EMPTY)
    relative = tuple((x - origin_x, y - origin_y) for x, y in cells)
    return Block(block_id, colors.pop(), relative, (origin_x, origin_y), ice, axis)


def parse_modifier(block_id, tag):
    if tag == EMPTY:
        return 0, None
    if tag == "-":
        return 0, HORIZONTAL
    if tag == "|":
        return 0, VERTICAL
    if tag.startswith("i") and tag[1:].isdigit():
        return int(tag[1:]), None
    raise LevelFormatError(f"block {block_id!r} has unknown modifier {tag!r}")


def parse_gates(color, ids, width, height):
    border = [
        (TOP, [(ids[0][x + 1], color[0][x + 1]) for x in range(width)]),
        (BOTTOM, [(ids[height + 1][x + 1], color[height + 1][x + 1]) for x in range(width)]),
        (LEFT, [(ids[y + 1][0], color[y + 1][0]) for y in range(height)]),
        (RIGHT, [(ids[y + 1][width + 1], color[y + 1][width + 1]) for y in range(height)]),
    ]
    gates = []
    for side, cells in border:
        gates.extend(gates_along_side(side, cells))
    return gates


def gates_along_side(side, cells):
    gates = []
    for position, (gate_id, gate_color) in enumerate(cells):
        if gate_id in (EMPTY, WALL):
            continue
        if gate_color in (EMPTY, WALL):
            raise LevelFormatError(f"gate {gate_id!r} on {side} border at offset {position} has no color")
        previous = gates[-1] if gates else None
        if previous and previous.id == gate_id and previous.start + previous.length == position:
            if previous.color != gate_color:
                raise LevelFormatError(f"gate {gate_id!r} on {side} border has inconsistent colors")
            gates[-1] = Gate(gate_id, gate_color, side, previous.start, previous.length + 1)
        else:
            gates.append(Gate(gate_id, gate_color, side, position, 1))
    return gates
