import pytest

from core.validator import InvalidSolution, validate_solution
from tests.support import fixture_level, slides


def test_valid_solution_ends_in_a_win():
    level = fixture_level("test1")
    state = validate_solution(level, slides("1 2 0", "0 0 3"))
    assert state.exit_mask.bit_count() == 2


def test_illegal_slide_is_rejected_with_its_move_number():
    level = fixture_level("test1")
    with pytest.raises(InvalidSolution, match="move 1 \\(0 2 2\\)"):
        validate_solution(level, slides("0 2 2"))


def test_incomplete_solution_is_rejected():
    level = fixture_level("test1")
    with pytest.raises(InvalidSolution, match="not solved"):
        validate_solution(level, slides("1 2 0"))


def test_unknown_block_id_is_rejected():
    level = fixture_level("test1")
    with pytest.raises(InvalidSolution, match="no block with id 'Z'"):
        validate_solution(level, slides("Z 0 0"))


def test_slide_outside_the_board_is_rejected():
    level = fixture_level("test1")
    with pytest.raises(InvalidSolution, match="outside the board"):
        validate_solution(level, slides("0 -3 0"))
