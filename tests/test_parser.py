import pytest

from core.model import BOTTOM, HORIZONTAL, LEFT, RIGHT, TOP
from core.parser import LevelFormatError, parse_level
from tests.support import FIXTURE_NAMES, fixture_level, fixture_text, level_from

EXIT_SIDES = {"t": TOP, "b": BOTTOM, "l": LEFT, "r": RIGHT}
EXIT_COLOR_TOKENS = {"LP": "p", "LG": "g", "DB": "B", "LB": "b", "DG": "G"}


def exits_table(text):
    rows = text.split("EXITS:")[1].strip().splitlines()
    gates = set()
    for row in rows:
        gate_id, color, side, x, y, length = row.split()
        start = int(x) if side in "tb" else int(y)
        gates.add((gate_id, EXIT_COLOR_TOKENS.get(color, color), EXIT_SIDES[side], start, int(length)))
    return gates


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_gates_match_exits_table(name):
    level = fixture_level(name)
    parsed = {(g.id, g.color, g.side, g.start, g.length) for g in level.gates}
    assert parsed == exits_table(fixture_text(name))


@pytest.mark.parametrize(
    "name, width, height, block_count",
    [("test1", 4, 5, 2), ("test2", 6, 6, 8), ("test3", 6, 6, 10), ("test4", 6, 6, 14), ("test5", 3, 7, 14)],
)
def test_fixture_dimensions_and_block_counts(name, width, height, block_count):
    level = fixture_level(name)
    assert (level.width, level.height, len(level.blocks)) == (width, height, block_count)


def test_block_c_in_test4_tags_its_row_major_first_cell():
    level = fixture_level("test4")
    block = level.blocks[level.block_index("C")]
    assert block.origin == (0, 1)
    assert block.tag_offset == (1, 0)
    assert block.ice == 2
    assert set(block.cells) == {(1, 0), (0, 1), (1, 1)}


def test_directional_blocks_in_test4_are_horizontal_only():
    level = fixture_level("test4")
    assert {b.id for b in level.blocks if b.axis == HORIZONTAL} == {"0", "1", "2", "3"}


def test_wall_shown_in_all_three_layers_is_a_wall_not_a_block():
    level = fixture_level("test4")
    assert level.walls >> level.anchor_index(5, 0) & 1
    assert level.walls >> level.anchor_index(0, 5) & 1
    assert {b.id for b in level.blocks}.isdisjoint({"#"})


def test_undocumented_color_token_is_accepted():
    level = fixture_level("test1")
    assert level.blocks[level.block_index("0")].color == "p"


def test_row_with_wrong_token_count_reports_line_number():
    text = fixture_text("test1").replace(". p p g g .", ". p p g g", 1)
    with pytest.raises(LevelFormatError, match="line 9"):
        parse_level(text)


def test_missing_modifiers_section_raises():
    text = fixture_text("test1").split("MODIFIERS:")[0]
    with pytest.raises(LevelFormatError, match="MODIFIERS:"):
        parse_level(text)


def test_block_with_conflicting_colors_raises():
    level_text = """
        w=2
        h=1
        COLOR:
        . . . .
        . R Y .
        . . . .
        ID:
        . . . .
        . 0 0 .
        . . . .
        MODIFIERS:
        . . . .
        . . . .
        . . . .
    """
    with pytest.raises(LevelFormatError, match="block '0'"):
        level_from(level_text)


def test_adjacent_gates_with_different_ids_stay_separate():
    level = level_from("""
        w=2
        h=1
        COLOR:
        . R R .
        . . . .
        . . . .
        ID:
        . a b .
        . . . .
        . . . .
        MODIFIERS:
        . ^ ^ .
        . . . .
        . . . .
    """)
    assert [(g.id, g.start, g.length) for g in level.gates] == [("a", 0, 1), ("b", 1, 1)]
