from typing import NamedTuple


class Slide(NamedTuple):
    block_id: str
    x: int
    y: int

    def __str__(self):
        return f"{self.block_id} {self.x} {self.y}"


def move_to_slide(level, move):
    block, anchor = move
    ax, ay = level.anchor_position(anchor)
    dx, dy = level.blocks[block].tag_offset
    return Slide(level.blocks[block].id, ax + dx, ay + dy)


def slide_to_move(level, slide):
    block = level.block_index(slide.block_id)
    dx, dy = level.blocks[block].tag_offset
    ax, ay = slide.x - dx, slide.y - dy
    if not (0 <= ax < level.width and 0 <= ay < level.height):
        raise ValueError(f"slide {slide} places block anchor at ({ax}, {ay}), outside the board")
    return block, level.anchor_index(ax, ay)


def parse_slide(line):
    block_id, x, y = line.split()
    return Slide(block_id, int(x), int(y))
