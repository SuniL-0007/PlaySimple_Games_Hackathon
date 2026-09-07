from core.simulator import apply_move
from core.state import initial_state
from tests.support import has_exited, level_from


def slide_up_to_top(level, block_id):
    block = level.blocks[level.block_index(block_id)]
    move = (level.block_index(block_id), level.anchor_index(block.origin[0], 0))
    return apply_move(level, initial_state(level), move)


def test_block_wider_than_gate_cannot_exit():
    level = level_from("""
        w=3
        h=2
        COLOR:
        . R . . .
        . . . . .
        . R R . .
        . . . . .
        ID:
        . a . . .
        . . . . .
        . 0 0 . .
        . . . . .
        MODIFIERS:
        . ^ . . .
        . . . . .
        . . . . .
        . . . . .
    """)
    assert not has_exited(level, slide_up_to_top(level, "0"), "0")


def test_block_spanning_two_gates_with_different_ids_cannot_exit():
    level = level_from("""
        w=3
        h=2
        COLOR:
        . R R . .
        . . . . .
        . R R . .
        . . . . .
        ID:
        . a b . .
        . . . . .
        . 0 0 . .
        . . . . .
        MODIFIERS:
        . ^ ^ . .
        . . . . .
        . . . . .
        . . . . .
    """)
    assert not has_exited(level, slide_up_to_top(level, "0"), "0")


def test_block_within_wider_gate_exits():
    level = level_from("""
        w=3
        h=2
        COLOR:
        . R R R .
        . . . . .
        . . R . .
        . . . . .
        ID:
        . a a a .
        . . . . .
        . . 0 . .
        . . . . .
        MODIFIERS:
        . ^ ^ ^ .
        . . . . .
        . . . . .
        . . . . .
    """)
    assert has_exited(level, slide_up_to_top(level, "0"), "0")


def test_wrong_color_gate_does_not_release_block():
    level = level_from("""
        w=1
        h=2
        COLOR:
        . Y .
        . . .
        . R .
        . . .
        ID:
        . a .
        . . .
        . 0 .
        . . .
        MODIFIERS:
        . ^ .
        . . .
        . . .
        . . .
    """)
    assert not has_exited(level, slide_up_to_top(level, "0"), "0")


CONCAVE_SHAPE_UNDER_TOP_GATE = """
    w=3
    h=3
    COLOR:
    . R R . .
    . . . . .
    . R . . .
    . R R . .
    . . . . .
    ID:
    . a a . .
    . . . . .
    . 0 . . .
    . 0 0 . .
    . . . . .
    MODIFIERS:
    . ^ ^ . .
    . . . . .
    . . . . .
    . . . . .
    . . . . .
"""


def test_concave_shape_exits_when_its_shadow_is_clear():
    level = level_from(CONCAVE_SHAPE_UNDER_TOP_GATE)
    assert has_exited(level, slide_up_to_top(level, "0"), "0")


def test_concave_shape_cannot_exit_when_another_block_sits_in_its_shadow():
    level = level_from("""
        w=3
        h=3
        COLOR:
        . R R . .
        . . Y . .
        . R . . .
        . R R . .
        . . . . .
        ID:
        . a a . .
        . . 1 . .
        . 0 . . .
        . 0 0 . .
        . . . . .
        MODIFIERS:
        . ^ ^ . .
        . . . . .
        . . . . .
        . . . . .
        . . . . .
    """)
    state = apply_move(level, initial_state(level), (level.block_index("0"), level.anchor_index(0, 0)))
    assert not has_exited(level, state, "0")


def test_block_exits_sideways_through_left_gate():
    level = level_from("""
        w=3
        h=1
        COLOR:
        . . . . .
        B . . B .
        . . . . .
        ID:
        . . . . .
        a . . 0 .
        . . . . .
        MODIFIERS:
        . . . . .
        < . . . .
        . . . . .
    """)
    state = apply_move(level, initial_state(level), (level.block_index("0"), level.anchor_index(0, 0)))
    assert has_exited(level, state, "0")


def test_block_aligned_with_gate_but_not_touching_edge_stays():
    level = level_from("""
        w=1
        h=3
        COLOR:
        . R .
        . . .
        . . .
        . R .
        . . .
        ID:
        . a .
        . . .
        . . .
        . 0 .
        . . .
        MODIFIERS:
        . ^ .
        . . .
        . . .
        . . .
        . . .
    """)
    state = apply_move(level, initial_state(level), (level.block_index("0"), level.anchor_index(0, 1)))
    assert not has_exited(level, state, "0")
