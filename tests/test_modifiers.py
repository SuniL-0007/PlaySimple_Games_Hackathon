from core.notation import Slide, move_to_slide, slide_to_move
from core.simulator import apply_move
from core.state import initial_state
from tests.support import fixture_level, has_exited, level_from, slides_of

ICE_AND_DIRECTIONAL = """
    w=3
    h=3
    COLOR:
    . Y . . .
    . . . R .
    . Y R . .
    . . . B .
    . . . . .
    ID:
    . a . . .
    . . . 2 .
    . 1 0 . .
    . . . 3 .
    . . . . .
    MODIFIERS:
    . ^ . . .
    . . . | .
    . . i1 . .
    . . . - .
    . . . . .
"""


def test_frozen_block_cannot_move_until_enough_blocks_have_exited():
    level = level_from(ICE_AND_DIRECTIONAL)
    assert not any(slide.startswith("0 ") for slide in slides_of(level, initial_state(level)))
    move = (level.block_index("1"), level.anchor_index(0, 0))
    unlocked = apply_move(level, initial_state(level), move)
    assert has_exited(level, unlocked, "1")
    zero_slides = {slide for slide in slides_of(level, unlocked) if slide.startswith("0 ")}
    assert zero_slides == {"0 0 1", "0 2 1", "0 1 0", "0 1 2"}


def test_vertical_only_block_slides_only_up_and_down():
    level = level_from(ICE_AND_DIRECTIONAL)
    assert {slide for slide in slides_of(level, initial_state(level)) if slide.startswith("2 ")} == {"2 2 1"}


def test_horizontal_only_block_slides_only_left_and_right():
    level = level_from(ICE_AND_DIRECTIONAL)
    three_slides = {slide for slide in slides_of(level, initial_state(level)) if slide.startswith("3 ")}
    assert three_slides == {"3 1 2", "3 0 2"}


def test_horizontal_only_block_cannot_exit_through_top_gate():
    level = level_from("""
        w=1
        h=2
        COLOR:
        . R .
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
        . - .
        . . .
    """)
    assert slides_of(level, initial_state(level)) == set()
    assert level.exit_anchors[level.block_index("0")] == ()


def test_slides_report_the_tag_cell_of_ra_br_shapes():
    level = fixture_level("test4")
    block = level.block_index("C")
    slide = move_to_slide(level, (block, level.anchor_index(3, 1)))
    assert slide == Slide("C", 4, 1)
    assert slide_to_move(level, slide) == (block, level.anchor_index(3, 1))


def test_initial_tag_cell_of_block_c_matches_its_modifier_position():
    level = fixture_level("test4")
    block = level.block_index("C")
    move = (block, initial_state(level).anchors[block])
    assert move_to_slide(level, move) == Slide("C", 1, 1)
