import argparse
import random
import string
from pathlib import Path

COLORS = "YRPOTBbGg"
SHAPES = {
    "1x1": ((0, 0),),
    "2x1_H": ((0, 0), (1, 0)),
    "2x1_V": ((0, 0), (0, 1)),
    "3x1_H": ((0, 0), (1, 0), (2, 0)),
    "2x2": ((0, 0), (1, 0), (0, 1), (1, 1)),
    "RA_TL": ((0, 0), (1, 0), (0, 1)),
    "RA_TR": ((0, 0), (1, 0), (1, 1)),
    "RA_BL": ((0, 0), (0, 1), (1, 1)),
    "RA_BR": ((1, 0), (0, 1), (1, 1)),
}
BLOCK_IDS = string.digits + string.ascii_uppercase
GATE_IDS = string.ascii_lowercase


def place_blocks(width, height, count, rng, occupied):
    blocks = []
    attempts = 0
    while len(blocks) < count and attempts < 2000:
        attempts += 1
        shape = rng.choice(list(SHAPES.values()))
        ax = rng.randrange(width - max(dx for dx, _ in shape))
        ay = rng.randrange(height - max(dy for _, dy in shape))
        cells = [(ax + dx, ay + dy) for dx, dy in shape]
        if any(cell in occupied for cell in cells):
            continue
        occupied.update(cells)
        blocks.append((BLOCK_IDS[len(blocks)], rng.choice(COLORS[:4]), cells))
    return blocks


def place_walls(width, height, count, rng):
    return {(rng.randrange(width), rng.randrange(height)) for _ in range(count)}


def extent(cells, side):
    axis = 0 if side in "tb" else 1
    return 1 + max(cell[axis] for cell in cells) - min(cell[axis] for cell in cells)


def place_gates(width, height, blocks, rng):
    gates = []
    used = set()
    for color in sorted({color for _, color, _ in blocks}):
        for _ in range(20):
            side = rng.choice("tblr")
            length = max(extent(cells, side) for _, c, cells in blocks if c == color) + rng.choice((0, 1))
            limit = width if side in "tb" else height
            start = rng.randrange(limit - length + 1)
            span = {(side, position) for position in range(start, start + length)}
            if span & used:
                continue
            used |= span
            gates.append((GATE_IDS[len(gates)], color, side, start, length))
            break
    return gates


def render(width, height, walls, blocks, gates):
    color = [["."] * (width + 2) for _ in range(height + 2)]
    ids = [["."] * (width + 2) for _ in range(height + 2)]
    modifiers = [["."] * (width + 2) for _ in range(height + 2)]
    for x, y in walls:
        color[y + 1][x + 1] = "#"
    for block_id, block_color, cells in blocks:
        for x, y in cells:
            color[y + 1][x + 1] = block_color
            ids[y + 1][x + 1] = block_id
    arrows = {"t": "^", "b": "v", "l": "<", "r": ">"}
    for gate_id, gate_color, side, start, length in gates:
        for position in range(start, start + length):
            x, y = border_cell(width, height, side, position)
            color[y][x] = gate_color
            ids[y][x] = gate_id
            modifiers[y][x] = arrows[side]
    grids = "\n\n".join(
        f"{name}\n" + "\n".join(" ".join(row) for row in grid)
        for name, grid in (("COLOR:", color), ("ID:", ids), ("MODIFIERS:", modifiers))
    )
    return f"ASCII\nw={width}\nh={height}\n\n{grids}\n"


def border_cell(width, height, side, position):
    if side == "t":
        return position + 1, 0
    if side == "b":
        return position + 1, height + 1
    if side == "l":
        return 0, position + 1
    return width + 1, position + 1


def generate(width, height, blocks, walls, seed):
    rng = random.Random(seed)
    wall_cells = place_walls(width, height, walls, rng)
    placed = place_blocks(width, height, blocks, rng, set(wall_cells))
    return render(width, height, wall_cells, placed, place_gates(width, height, placed, rng))


def main():
    parser = argparse.ArgumentParser(description="generate random stress levels")
    parser.add_argument("output_dir")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--width", type=int, default=12)
    parser.add_argument("--height", type=int, default=12)
    parser.add_argument("--blocks", type=int, default=25)
    parser.add_argument("--walls", type=int, default=4)
    parser.add_argument("--seed", type=int, default=1)
    arguments = parser.parse_args()
    output = Path(arguments.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for offset in range(arguments.count):
        seed = arguments.seed + offset
        text = generate(arguments.width, arguments.height, arguments.blocks, arguments.walls, seed)
        name = f"stress_{arguments.width}x{arguments.height}_b{arguments.blocks}_s{seed}.txt"
        (output / name).write_text(text)


if __name__ == "__main__":
    main()
