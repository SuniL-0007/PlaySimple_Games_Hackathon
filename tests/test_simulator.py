from core.simulator import apply_move, is_goal
from core.state import initial_state
from tests.support import fixture_level, has_exited, with_block_at


def test_block_reaching_matching_gate_exits_immediately():
    level = fixture_level("test1")
    state = apply_move(level, initial_state(level), (level.block_index("1"), level.anchor_index(2, 0)))
    assert has_exited(level, state, "1")
    assert state.anchors[level.block_index("1")] == level.exited_anchor
    assert not has_exited(level, state, "0")


def test_no_auto_exit_before_the_first_move():
    level = fixture_level("test5")
    assert initial_state(level).exit_mask == 0


def test_ice_block_on_its_gate_leaves_in_the_same_cascade_as_the_unlocking_exit():
    level = fixture_level("test5")
    staged = with_block_at(level, initial_state(level), "A", 2, 1)
    state = apply_move(level, staged, (level.block_index("A"), level.anchor_index(2, 0)))
    assert has_exited(level, state, "A")
    assert has_exited(level, state, "9")
    assert state.exit_mask.bit_count() == 2


def test_block_exits_through_gate_cleared_by_earlier_cascade():
    level = fixture_level("test5")
    staged = with_block_at(level, initial_state(level), "A", 2, 1)
    state = apply_move(level, staged, (level.block_index("A"), level.anchor_index(2, 0)))
    state = apply_move(level, state, (level.block_index("B"), level.anchor_index(0, 0)))
    assert has_exited(level, state, "B")


def test_goal_requires_every_block_with_a_matching_gate_to_exit():
    level = fixture_level("test1")
    state = apply_move(level, initial_state(level), (level.block_index("1"), level.anchor_index(2, 0)))
    assert not is_goal(level, state)
    state = apply_move(level, state, (level.block_index("0"), level.anchor_index(0, 3)))
    assert is_goal(level, state)
