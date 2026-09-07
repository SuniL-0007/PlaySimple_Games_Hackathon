import argparse
import sys
import time
from pathlib import Path

from core.notation import move_to_slide
from core.parser import parse_level
from core.validator import validate_solution
from search import anytime, bfs, complete, fast
from search.result import SOLVED

TOTAL_BUDGET_SECONDS = 45.0
RESULTS_DIR = Path("results")

SOLVERS = {"auto": anytime.solve, "complete": complete.solve, "fast": fast.solve, "bfs": bfs.solve}


def parse_arguments(argv):
    parser = argparse.ArgumentParser(description="Color Block Crush solver")
    parser.add_argument("level", help="path to a level file in the ASCII format")
    parser.add_argument("--solver", choices=tuple(SOLVERS), default="auto")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def timed(name, solver, level, deadline, verbose):
    started = time.monotonic()
    result = solver(level, deadline)
    if verbose:
        report(name, result, time.monotonic() - started)
    return result


def report(name, result, elapsed):
    for weight, guide_weight, moves, expanded, seconds in result.improvements:
        print(
            f"{name}: improvement weight={weight} guide_weight={guide_weight} "
            f"moves={moves} expanded={expanded:,} seconds={seconds:.2f}",
            file=sys.stderr,
        )
    print(
        f"{name}: status={result.status} moves={len(result.moves)} "
        f"expanded={result.expanded:,} generated={result.generated:,} "
        f"unique_states={result.stored:,} seconds={elapsed:.2f} optimal={result.optimal}",
        file=sys.stderr,
    )


def run(argv):
    deadline = time.monotonic() + TOTAL_BUDGET_SECONDS
    arguments = parse_arguments(argv)
    level = parse_level(Path(arguments.level).read_text())
    result = timed(arguments.solver, SOLVERS[arguments.solver], level, deadline, arguments.verbose)
    return level, result, arguments


def render(level, result):
    slides = [move_to_slide(level, move) for move in result.moves]
    if result.status == SOLVED:
        validate_solution(level, slides)
    lines = [f"STATUS: {result.status}", f"MOVES: {len(slides)}"]
    lines.extend(str(slide) for slide in slides)
    return "\n".join(lines)


def save_result(level_path, solver, output):
    RESULTS_DIR.mkdir(exist_ok=True)
    name = f"{Path(level_path).stem}_{solver}.txt"
    (RESULTS_DIR / name).write_text(output + "\n")


def main(argv=None):
    level, result, arguments = run(sys.argv[1:] if argv is None else argv)
    output = render(level, result)
    print(output)
    save_result(arguments.level, arguments.solver, output)


if __name__ == "__main__":
    main()
