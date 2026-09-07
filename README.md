# Color Block Crush

A sliding-block puzzle where colored polyominoes slide across a grid — never rotate,
never stop halfway on their own — until they hit a wall, another block, or a gate of
their own color on the border. Some blocks won't leave until N others already have.
Some can only ever slide along one axis. Releasing one block can clear the path for
another mid-move, and that cascade has to resolve correctly or the puzzle looks
unsolvable when it isn't. This repo is three different ways of solving it, plus the
evidence for why each one exists.

## Running it

```
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python solve.py tests/fixtures/test4.txt
```

`stdout` is nothing but the answer: a status line, a move count, then one
`<block_id> <x> <y>` per move. Every run is also written to
`results/<level>_<solver>.txt`, because scrolling back through a terminal to find what a
level solved to gets old fast.

```
STATUS: SOLVED
MOVES: 49
C 3 7
...
```

Pass `--solver complete`, `--solver fast`, or `--solver bfs` to pick a specific engine;
leave it off and you get `auto`, which is what you actually want most of the time.

## Three solvers

**`complete`** is A\* with an admissible heuristic — a per-block relaxed-slide distance,
computed once with a backward BFS over a walls-only board. It's provably shortest when
it finds a solution, and it's the only one of the three that can prove a level
unsolvable. The cost is that it's exhaustive: on a busy board it can expand hundreds of
thousands of states, and on a genuinely hard one it runs out of memory before it runs out
of time.

**`fast`** is the same search engine at a much greedier weight, steered by a
hand-built heuristic that looks at which blocks are currently sitting in another block's
way — and, one level deeper, which blocks are blocking those. It gives up 10 to 15
percent more moves in exchange for finishing in a few seconds instead of twenty, and on
the boards where `complete` can't finish at all, it's the difference between an answer
and nothing.

**`auto`** doesn't pick one of the above — it runs both, in the same search, without
throwing away the work in between. It starts as greedy as `fast`, then walks a
weight schedule down toward `complete`'s exact guarantee, refining the same open list the
whole way instead of restarting from scratch. Every level in the assignment's five test
cases gets solved to the certified-optimal answer this way. On the levels that break
`complete` outright, it still comes back with something — usually a shorter something
than `fast` alone would have found.

## Results

The five levels from the assignment, solved by all three engines (Python 3.12, one core,
seconds are wall clock):

| level | complete | fast | auto |
|---|---|---|---|
| test1 | 2 moves, 0.00s | 2 moves, 0.00s | 2 moves, 0.00s |
| test2 | 10 moves, 0.00s | 11 moves, 0.01s | 10 moves, 0.01s |
| test3 | 24 moves, 4.0s | 32 moves, 0.1s | 24 moves, 5.4s |
| test4 | 49 moves, 16-20s | 58 moves, 3.5s | 49 moves, 20-21s |
| test5 | 43 moves, 0.6s | 53 moves, 2.6s | 43 moves, 5.0s |

`auto` matches `complete`'s move count on every single one — and it costs more wall time
doing it on the levels `complete` was already fast on. That's the honest trade, not a
hidden one.

The interesting numbers show up on harder boards. Generate 20 random 12x12 levels with 25
blocks each (`benchmarks/generate.py`) and run all three solvers with a 50-second budget:
**`complete` solves zero of them.** It hits a 2.5-million-state memory ceiling before its
clock runs out, every time. `fast` and `auto` both solve the same 14 out of 20 — same
solvability, no losses — but `auto` beats `fast`'s move count on all 14:

| level | fast | auto | saved |
|---|---|---|---|
| s1 | 84 | 83 | 1 |
| s3 | 81 | 79 | 2 |
| s4 | 106 | 104 | 2 |
| s5 | 55 | 53 | 2 |
| s7 | 103 | 101 | 2 |
| s10 | 93 | 88 | 5 |
| s11 | 61 | 59 | 2 |
| s12 | 77 | 75 | 2 |
| s14 | 92 | 90 | 2 |
| s16 | 69 | 67 | 2 |
| s17 | 84 | 82 | 2 |
| s18 | 109 | 107 | 2 |
| s19 | 101 | 99 | 2 |
| s20 | 90 | 79 | 11 |

The other six levels time out for everyone — that's a real limit of this approach on
boards dense enough, not something either heuristic papers over.

## Why it's built this way

`DESIGN.md` walks through the state representation, the move generator, and the search
engine in more depth than belongs here. `TRADEOFFS.md` is the argument for why these
three algorithms specifically, including the ones that got measured and rejected —
bidirectional search, beam search, planning as SAT, a few others. `LEARN.md` is the long
version of both, written up for interview prep, with the bug this project actually found
during stress testing and how it got fixed.
