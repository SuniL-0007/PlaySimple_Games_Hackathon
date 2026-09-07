import time
from pathlib import Path

import pytest

from core.parser import parse_level
from search import anytime, complete, fast
from search.result import SOLVED, TIMEOUT, UNSOLVABLE

FIXTURES = sorted((Path(__file__).resolve().parent.parent / "tests" / "fixtures").glob("test*.txt"))
BUDGET_SECONDS = 50.0
SOLVERS = {"auto": anytime.solve, "complete": complete.solve, "fast": fast.solve}


@pytest.mark.parametrize("solver_name", sorted(SOLVERS))
@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda path: path.stem)
def test_solver_speed(benchmark, fixture, solver_name):
    level = parse_level(fixture.read_text())
    solver = SOLVERS[solver_name]
    benchmark.group = fixture.stem
    result = benchmark.pedantic(
        lambda: solver(level, time.monotonic() + BUDGET_SECONDS), rounds=1, iterations=1
    )
    assert result.status in (SOLVED, UNSOLVABLE, TIMEOUT)
