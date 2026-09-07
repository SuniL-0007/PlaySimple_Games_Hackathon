import subprocess
import sys
import time
from pathlib import Path

import pytest

from core.notation import move_to_slide, parse_slide
from core.validator import validate_solution
from search import anytime, complete, fast
from search.result import SOLVED, TIMEOUT, UNSOLVABLE
from tests.support import FIXTURE_NAMES, FIXTURES, fixture_level, level_from

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOLVERS = {"complete": complete.solve, "fast": fast.solve, "auto": anytime.solve}
SHORTEST_MOVES = {"test1": 2, "test2": 10, "test3": 24, "test4": 49, "test5": 43}
EXPIRED = time.monotonic() - 1
SHORT_BUDGET = 0.3


def solve_and_validate(level, solver, deadline=None):
    result = solver(level, time.monotonic() + 50 if deadline is None else deadline)
    assert result.status == SOLVED
    validate_solution(level, [move_to_slide(level, move) for move in result.moves])
    return result


@pytest.mark.parametrize("name", FIXTURE_NAMES)
@pytest.mark.parametrize("solver", ("complete", "fast"))
def test_fixture_is_solved_with_a_valid_solution(name, solver):
    solve_and_validate(fixture_level(name), SOLVERS[solver])


@pytest.mark.parametrize("name, optimal", [("test1", 2), ("test2", 10)])
def test_complete_solver_returns_shortest_solution(name, optimal):
    assert len(solve_and_validate(fixture_level(name), complete.solve).moves) == optimal


@pytest.mark.parametrize("name, optimal", sorted(SHORTEST_MOVES.items()))
def test_auto_solver_certifies_the_shortest_solution(name, optimal):
    result = solve_and_validate(fixture_level(name), anytime.solve)
    assert (len(result.moves), result.optimal) == (optimal, True)


def test_auto_solver_records_each_improvement_in_schedule_order():
    result = solve_and_validate(fixture_level("test2"), anytime.solve)
    phases = [(weight, guide_weight, moves) for weight, guide_weight, moves, _, _ in result.improvements]
    assert phases == [(3.0, 3.0, 11), (2.0, 2.0, 10)]


def test_auto_solver_returns_its_best_incumbent_when_the_deadline_expires():
    deadline = time.monotonic() + SHORT_BUDGET
    result = solve_and_validate(fixture_level("test3"), anytime.solve, deadline)
    latest_moves = result.improvements[-1][2]
    assert (len(result.moves), result.optimal) == (latest_moves, False)
    assert latest_moves < result.improvements[0][2]


def test_auto_solver_times_out_when_the_deadline_expires_before_any_incumbent():
    result = anytime.solve(fixture_level("test4"), EXPIRED)
    assert (result.status, result.moves, result.improvements) == (TIMEOUT, (), ())


def test_auto_solver_skips_retargeting_once_the_deadline_has_passed():
    result = solve_and_validate(fixture_level("test2"), anytime.solve, EXPIRED)
    assert (len(result.moves), result.optimal, len(result.improvements)) == (11, False, 1)
    assert result.expanded == result.improvements[-1][3]


def test_only_admissible_searches_certify_optimality():
    level = fixture_level("test2")
    certified = {name: solve_and_validate(level, solver).optimal for name, solver in SOLVERS.items()}
    assert certified == {"complete": True, "fast": False, "auto": True}


def test_level_with_no_matching_gates_is_already_solved():
    level = level_from("""
        w=2
        h=1
        COLOR:
        . Y . .
        . R . .
        . . . .
        ID:
        . a . .
        . 0 . .
        . . . .
        MODIFIERS:
        . ^ . .
        . . . .
        . . . .
    """)
    for solver in SOLVERS.values():
        result = solver(level, time.monotonic() + 5)
        assert (result.status, result.moves) == (SOLVED, ())


WALLED_OFF_GATE = """
    w=3
    h=3
    COLOR:
    . . R . .
    . . . . .
    . # # # .
    . . R . .
    . . . . .
    ID:
    . . a . .
    . . . . .
    . # # # .
    . . 0 . .
    . . . . .
    MODIFIERS:
    . . ^ . .
    . . . . .
    . # # # .
    . . . . .
    . . . . .
"""


@pytest.mark.parametrize("solver", SOLVERS)
def test_unreachable_gate_is_reported_unsolvable(solver):
    assert SOLVERS[solver](level_from(WALLED_OFF_GATE), time.monotonic() + 5).status == UNSOLVABLE


def run_cli(*arguments):
    return subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "solve.py"), *arguments],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        check=True,
    )


def test_cli_prints_only_the_solution_contract_on_stdout():
    completed = run_cli(str(FIXTURES / "test1.txt"), "--solver", "complete")
    lines = completed.stdout.splitlines()
    assert lines[:2] == ["STATUS: SOLVED", "MOVES: 2"]
    validate_solution(fixture_level("test1"), [parse_slide(line) for line in lines[2:]])
    assert completed.stderr == ""


def test_cli_verbose_logs_to_stderr_only():
    completed = run_cli(str(FIXTURES / "test1.txt"), "--solver", "fast", "--verbose")
    assert completed.stdout.splitlines()[0] == "STATUS: SOLVED"
    assert "fast: status=SOLVED" in completed.stderr


def test_cli_verbose_reports_improvements_and_certification():
    completed = run_cli(str(FIXTURES / "test2.txt"), "--verbose")
    assert "auto: improvement weight=3.0 guide_weight=3.0 moves=11" in completed.stderr
    assert "auto: status=SOLVED moves=10" in completed.stderr
    assert "optimal=True" in completed.stderr


def test_cli_default_solver_solves_with_shortest_known_solution():
    completed = run_cli(str(FIXTURES / "test2.txt"))
    assert completed.stdout.splitlines()[:2] == ["STATUS: SOLVED", "MOVES: 10"]


def test_cli_saves_the_result_to_disk():
    completed = run_cli(str(FIXTURES / "test1.txt"), "--solver", "complete")
    saved = (PROJECT_ROOT / "results" / "test1_complete.txt").read_text()
    assert saved == completed.stdout
