from core.moves import legal_moves
from core.simulator import apply_move
from core.state import initial_state
from tests.support import fixture_level, level_from, slides_of


def test_every_intermediate_stop_is_a_distinct_move():
    level = fixture_level("test1")
    assert slides_of(level, initial_state(level)) == {"0 0 0", "0 0 1", "0 0 3", "1 2 0", "1 2 2", "1 2 3"}


def test_slide_stops_before_wall():
    level = level_from("""
        w=4
        h=1
        COLOR:
        . . . . . .
        . R . # . .
        . . . . . .
        ID:
        . . . . . .
        . 0 . # . .
        . . . . . .
        MODIFIERS:
        . . . . . .
        . . . . . .
        . . . . . .
    """)
    assert slides_of(level, initial_state(level)) == {"0 1 0"}


def test_slide_stops_before_another_block():
    level = level_from("""
        w=1
        h=4
        COLOR:
        . . .
        . R .
        . . .
        . . .
        . Y .
        . . .
        ID:
        . . .
        . 0 .
        . . .
        . . .
        . 1 .
        . . .
        MODIFIERS:
        . . .
        . . .
        . . .
        . . .
        . . .
        . . .
    """)
    assert slides_of(level, initial_state(level)) == {"0 0 1", "0 0 2", "1 0 2", "1 0 1"}


def test_exited_block_has_no_moves():
    level = fixture_level("test1")
    state = apply_move(level, initial_state(level), (level.block_index("1"), level.anchor_index(2, 0)))
    assert {block for block, _ in legal_moves(level, state)} == {level.block_index("0")}
