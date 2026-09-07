import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.notation import move_to_slide
from core.parser import parse_level
from core.validator import validate_solution
from search import anytime, bfs, complete, fast
from search.result import SOLVED

SOLVERS = {"auto": anytime.solve, "complete": complete.solve, "fast": fast.solve, "bfs": bfs.solve}
FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


HEADER = ("level", "solver", "status", "moves", "expanded", "generated", "unique_states", "seconds")
NUMERIC_COLUMNS = {3, 4, 5, 6, 7}
STATUS_COLORS = {"SOLVED": "32", "TIMEOUT": "33", "UNSOLVABLE": "31"}


def benchmark(path, name, solver, budget):
    level = parse_level(path.read_text())
    started = time.monotonic()
    result = solver(level, started + budget)
    elapsed = time.monotonic() - started
    if result.status == SOLVED:
        validate_solution(level, [move_to_slide(level, move) for move in result.moves])
    return (
        path.name,
        name,
        result.status,
        f"{len(result.moves):,}",
        f"{result.expanded:,}",
        f"{result.generated:,}",
        f"{result.stored:,}",
        f"{elapsed:.2f}",
    )


def main():
    parser = argparse.ArgumentParser(description="benchmark solvers over level files")
    parser.add_argument("levels", nargs="*", help="extra level files; the five fixtures always run")
    parser.add_argument("--solvers", default="complete,fast")
    parser.add_argument("--budget", type=float, default=50.0)
    arguments = parser.parse_args()
    paths = sorted(FIXTURES.glob("test*.txt")) + [Path(p) for p in arguments.levels]
    solver_names = arguments.solvers.split(",")
    widths = column_widths(paths, solver_names)
    rows = [HEADER]
    print_row(HEADER, widths, color=False)
    print_row(["-" * width for width in widths], widths, color=False)
    for path in paths:
        for name in solver_names:
            row = benchmark(path, name, SOLVERS[name], arguments.budget)
            rows.append(row)
            print_row(row, widths, color=True)
    print()
    for row in rows:
        print_row(row, widths, color=False)


def column_widths(paths, solver_names):
    widths = [len(title) for title in HEADER]
    widths[0] = max(widths[0], *(len(path.name) for path in paths))
    widths[1] = max(widths[1], *(len(name) for name in solver_names))
    widths[2] = max(widths[2], len("UNSOLVABLE"))
    return widths


def print_row(row, widths, color):
    cells = []
    for index, (value, width) in enumerate(zip(row, widths, strict=True)):
        text = str(value)
        aligned = text.rjust(width) if index in NUMERIC_COLUMNS else text.ljust(width)
        if color and index == 2 and text in STATUS_COLORS and sys.stdout.isatty():
            aligned = f"\033[{STATUS_COLORS[text]}m{aligned}\033[0m"
        cells.append(aligned)
    print("  ".join(cells), flush=True)


if __name__ == "__main__":
    main()
