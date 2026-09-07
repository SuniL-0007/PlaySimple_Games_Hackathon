# Design notes

## State representation

A parsed `Level` is immutable: board size, a wall bitmask, the blocks (id, colour, cells
relative to the bounding-box corner, ice threshold, movement axis) and the gates (id,
colour, side, span). The board is a bitboard of `width * height` bits, so a block
placement is one integer and collision is one `&`.

A search `State` is `(anchors, exit_mask)`: one anchor per block (a cell index, or the
sentinel `width * height` once exited) plus a bitmask of exited blocks. Per-block tables
built once in `core/model.py` do the rest of the work: `masks[block][anchor]` is the
placement bitmask; `steps[block][direction][anchor]` is the next anchor one cell over
(`-1` at the edge, so a slide is a table walk); `exit_shadows[block][anchor]` is `None`
unless the block is colour-matched, fits a single gate's span, and (for directional
blocks) is on the allowed axis — in which case it holds the cells that must stay empty
between the block and that edge, handling concave shapes like `RA_BL`.

Interchangeable blocks (same colour, cells, ice, axis — Test 4 has four identical `DB
1x1`s, Test 5 has eight identical `Y 1x1`s) are grouped contiguously at build time so the
closed-set key can sort each group's slice instead of treating every permutation as a
distinct state; this removes a factor of `4!`/`8!` from the reachable space. Keys are
`bytes(anchors)` (with those slices sorted) rather than tuples, both for hashing speed
and to keep memory per stored state small — the engines cap stored states at 2.5 million
and return `TIMEOUT` instead of running out of memory.

## Move generation and transitions

`core/moves.py` slides every unfrozen block one cell at a time until the placement mask
hits a wall or another block, yielding **every intermediate stop** as its own move, not
just the farthest one — stopping only at the far end would make a `UNSOLVABLE` verdict
unsound, since some fixture solutions use partial slides. Ice blocks off a move
(`ice_threshold > exits`); directional blocks get a two-direction table instead of four.

`core/simulator.py` is the only module that knows the exit rules. `apply_move` places the
block, then runs a fixpoint: repeatedly release any block whose shadow is clear and whose
ice threshold is met, until nothing more releases. The threshold check has to live inside
that loop — in Test 5, block `9` (`ic=1`) sits on its own gate from the start and must
exit in the *same* cascade as block `A`, whose exit is what raises the count to 1; a
single before/after check would strand it and wrongly report the level unsolvable.

Printed moves report the block's row-major-first cell (its "tag" cell), not its
bounding-box corner — they differ for shapes like `RA_BR` (Test 4's block `C`: cells
`(1,1) (0,2) (1,2)`, tag at `(1,1)`, bbox corner at `(0,1)`). `core/validator.py` replays
every printed solution through the real engine before `solve.py` prints it.

## The three solvers

**`complete`** is A\* with a consistent, admissible heuristic (`heuristics/distance.py`):
for each block, a multi-source BFS backwards from its exit anchors over a walls-only
board gives the minimum slides it needs in isolation, and the sum over blocks still
pending never overestimates the real cost, since every real move reduces it by at most 1.
This makes the returned solution shortest, and exhausting the open list is a sound proof
of `UNSOLVABLE`. A plain-BFS baseline (`search/bfs.py`, no heuristic) is kept for
comparison — it solves Test 1 instantly and times out on everything else, which is the
evidence that the heuristic is doing real work, not just adding overhead.

**`fast`** is the same A\* engine, weight 3, with an inadmissible guide term
(`heuristics/combined.py`) added on top of the admissible distance: it looks at which
blocks currently sit in a pending block's path to its exit, and one level deeper, which
blocks sit in *those* blockers' paths (capped at depth 2). Distance alone times out on
Test 4 and on random 12x12/25-block levels; adding the guide solves both in a few thousand
expansions instead of millions, because it steers the search toward clearing obstructions
instead of only shrinking raw distance. The weight makes the estimate inadmissible, so
`fast` trades move count for speed but keeps the same closed set and move generator, so
its `UNSOLVABLE` verdict stays sound.

**`auto`** (the CLI default) is one `BestFirstSearch` run through a decreasing-weight
schedule — `(3,3) → (2,2) → (1.5,1.5) → (1,0)` — instead of running `fast` and then
restarting `complete` from scratch. A goal found mid-schedule becomes an incumbent: it
tightens an admissible-bound prune and the search keeps going on the *same* open list and
closed-set table into the next, less-greedy phase. There is no separate bookkeeping list
for reopened nodes (the usual extra machinery in this kind of anytime search) because this
engine never used a closed set to begin with — a cheaper path to an already-expanded state
is simply pushed again, which is exactly the operation that bookkeeping exists to defer.
An emptied open list with an incumbent present certifies that incumbent optimal at any
weight, since bound-pruning only ever uses the admissible term: nothing on a strictly
cheaper path could have been pruned or gone missing. `auto` reaches the certified-optimal
answer on all five fixtures below.

## How they compare

`benchmarks/benchmark.py --solvers complete,fast,auto --budget 50`, Python 3.12, one core
of a Linux laptop:

```
level      solver    status  moves  expanded  generated  seconds
test1.txt  complete  SOLVED  2      2         11         0.00
test1.txt  fast      SOLVED  2      2         11         0.00
test1.txt  auto      SOLVED  2      2         11         0.00
test2.txt  complete  SOLVED  10     10        155        0.00
test2.txt  fast      SOLVED  11     11        141        0.01
test2.txt  auto      SOLVED  10     20        299        0.01
test3.txt  complete  SOLVED  24     64301     763064     4.02
test3.txt  fast      SOLVED  32     327       2965       0.11
test3.txt  auto      SOLVED  24     74219     895830     5.42
test4.txt  complete  SOLVED  49     259396    2628083    16.61
test4.txt  fast      SOLVED  58     5807      79153      3.48
test4.txt  auto      SOLVED  49     264675    2700892    20.05
test5.txt  complete  SOLVED  43     16312     68899      0.62
test5.txt  fast      SOLVED  53     11439     51304      2.61
test5.txt  auto      SOLVED  43     34115     148219     5.02
```

`complete` is always optimal but costs 16-20s on Test 4 — close enough to the 60s grading
limit that a larger hidden level could time out on time alone, and separately, `complete`
hits a 2.5M-stored-state memory cap and returns `TIMEOUT` on harder synthetic levels before
that time limit is even reached. `fast` gives up 9-10 moves on the busy fixtures for a
6x-30x drop in expanded states and finishes everything in under 4s. `auto` matches
`complete`'s optimal move count on every fixture, at the cost of extra wall time on the
ones `complete` already solved quickly (0.62s → 5.02s on Test 5) — a real, measured
trade-off, not a strict win. The trade pays off exactly where it was built to: across 20
generated 12x12/25-block stress levels, `complete` solves 0/20 before hitting its memory
cap, while `auto` matches `fast`'s solvability (14/20) and beats its move count on every
one of those 14 (by 1 to 11 moves), because it keeps refining the same search instead of
throwing away `fast`'s tree and starting `complete` over from nothing.
