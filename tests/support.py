from pathlib import Path
from textwrap import dedent

from core.moves import legal_moves
from core.notation import move_to_slide, parse_slide
from core.parser import parse_level
from core.state import State

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE_NAMES = ("test1", "test2", "test3", "test4", "test5")


def fixture_text(name):
    return (FIXTURES / f"{name}.txt").read_text()


def fixture_level(name):
    return parse_level(fixture_text(name))


def level_from(text):
    return parse_level(dedent(text))


def slides_of(level, state):
    return {str(move_to_slide(level, move)) for move in legal_moves(level, state)}


def slides(*lines):
    return [parse_slide(line) for line in lines]


def with_block_at(level, state, block_id, x, y):
    anchors = bytearray(state.anchors)
    anchors[level.block_index(block_id)] = level.anchor_index(x, y)
    return State(bytes(anchors), state.exit_mask)


def has_exited(level, state, block_id):
    return bool(state.exit_mask >> level.block_index(block_id) & 1)
