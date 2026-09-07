# Trade-offs

Every number below was measured on this implementation (Python 3.12, one core of a Linux
laptop, single run each, so wall-clock times carry roughly +-20% noise; expansion and
generation counts are deterministic).

## 1. What the solver has to guarantee

The contract is ordered: a printed solution must replay correctly through the real engine,
then the solver must finish inside the time budget, and only then does move count matter.
`core/validator.py` replays every printed solution before `solve.py` emits it, so an
incorrect move list cannot leave the process silently.

`UNSOLVABLE` must be sound because the caller cannot distinguish "no solution exists" from
"the solver gave up". An unsound `UNSOLVABLE` is worse than a `TIMEOUT`: it looks like an
answer. The only way the engines report `UNSOLVABLE` is by exhausting an open list fed by a
move generator that yields every intermediate stop of every slide, pruned only by an
admissible estimate returning infinity (a block that cannot reach any gate on a walls-only
board). Weighted or guided phases never touch that verdict; they reorder the open list, they
do not remove anything from it.

## 2. A* with reopening instead of a CLOSED set

`search/astar.py` keeps one dict, `best_depth`, from canonical key to the shallowest depth
seen. A popped entry whose depth is worse than `best_depth[key]` is discarded, and a child
that improves on the recorded depth is pushed again. That is a reopening open list: it
costs nothing extra for a consistent heuristic (no node is ever reached at a better depth
after expansion) and it keeps weighted and guided searches correct without a separate
inconsistency list, since a shorter path to an already-expanded state just re-enters the
heap.

Keys are `bytes(anchors)` with each interchangeable group's slice sorted, so four identical
`DB 1x1` blocks in Test 4 and eight identical `Y 1x1` blocks in Test 5 do not multiply the
state space by 4! and 8!. Bytes hash faster and store smaller than tuples; Test 4's exact
search stores 308,054 keys. `MAX_STORED_STATES = 2,500,000` turns a runaway search into a
`TIMEOUT` (or the best incumbent so far) instead of an out-of-memory kill, which would lose
the incumbent and any output at all.

## 3. Per-block relaxed distance as the admissible estimate

`heuristics/distance.py` runs one multi-source BFS per block, backwards from its exit
anchors over a board that contains only walls, counting slides. Summing over blocks that
have not exited is admissible because a real move slides one block and reduces that block's
relaxed distance by at most one, and consistent for the same reason: `h(parent) <=
1 + h(child)` for every edge, and exits only remove non-negative terms. Consistency is what
makes the first goal popped at weight 1 optimal without ever reopening a state; being a sum
of independent per-block terms is what lets `expand()` update the estimate incrementally
(`shares[stop] - home`) when a move causes no cascade instead of recomputing it.

This is a pattern database with a one-block pattern and a walls-only abstraction, which is
why it is cheap and why it is weak on Test 3 and Test 4 (64,301 and 259,396 expansions at
weight 1): it never sees that two blocks stand in each other's way. Multi-block additive
pattern databases would see that; see section 10.

## 4. `fast`: a separate dependency and frozen guide term at weight 3

`fast` runs a single phase with priority `depth + 3.0 * distance + 3.0 * guide`, where the
guide (`heuristics/combined.py`) counts blocks sitting in a pending block's corridor to its
nearest exit, one level of blockers-of-blockers deep, plus blocks still frozen by ice. The
guide is not admissible and is stored separately from the admissible term so the engine can
use the admissible term alone for bound pruning and certification.

Against exact search the effect is large on the busy fixtures: Test 3 drops from 64,301 to
327 expansions (24 to 32 moves), Test 4 from 259,396 to 5,807 (49 to 58 moves), Test 5 from
16,312 to 11,439 (43 to 53 moves). Weight alone does not explain the Test 4 result: weight
3 on the distance term with no guide expands 253,367 states there (17.8 s, and it happens
to find 49 moves), so the guide is what makes Test 4 fast. It is not a general win. The
same guide-less weight-3 search expands 183 states on Test 3 (30 moves, against `fast`'s
327 and 32) and 16,903 on Test 5 (43 moves in 0.67 s, against `fast`'s 11,439 expansions,
53 moves and 2.6 s, because each guide evaluation costs more than the expansions it saves).
The guide earns its place on the one fixture that would otherwise take 18 s, and costs
moves and wall time on the two that would not. The refactor that split the two terms
changed no count: all ten `fast`/`complete` fixture rows are identical before and after.

## 5. `auto`: one anytime search instead of fast-then-complete

The old `auto` ran `fast` for up to 10 s, then started `complete` from scratch. The new one
(`search/anytime.py`) is a single `BestFirstSearch` driven through the schedule
`(3.0, 3.0) -> (2.0, 2.0) -> (1.5, 1.5) -> (1.0, 0.0)`. When a goal is popped in a weighted
phase it becomes the incumbent, `bound` is set to its depth, `retarget()` rebuilds the open
list under the next phase's weights (dropping entries that are stale or cannot beat the
bound), and the search continues on the same `best_depth` table and parent arrays. Nothing
is thrown away between phases. No INCONS list is needed because there is no CLOSED set: a
state reached more cheaply after expansion is simply pushed again (section 2), which is the
work an INCONS list exists to defer.

What is certified: a goal popped while the weights are `(1.0, 0.0)` is optimal, and an
open list that empties with an incumbent present proves the incumbent optimal at any
weight, since every state on a strictly cheaper path would satisfy `depth + h_adm < bound`
at its optimal depth and so could not have been pruned by the bound, could not have been
skipped as stale, and could not have had an infinite estimate. A goal popped in a weighted
phase is only an upper bound; on deadline or store exhaustion it is returned as `SOLVED`
with `optimal=False`. Measured: Test 3 goes 32 -> 31 -> 30 -> 24 moves (incumbents at 327,
381, 9,953 and 74,219 expansions; 5.6 s total against 4.0 s for `complete` alone in the same
session). Test 4 goes 58 -> 57 -> 56 -> 49 (5,807 / 5,810 / 5,818 / 264,675 expansions;
19.8 s against 15.4 s). Test 5 goes 53 -> 47 -> 46 -> 43 (11,439 / 17,147 / 20,812 / 34,115;
5.2 s against 0.7 s). The weighted phases add 2-15% expansions over `complete` on the two
hard fixtures, and the bound from a 56-move incumbent prunes almost nothing from an exact
search whose frontier never exceeds f = 49; the win is that an answer exists after 0.1 s
on Test 3 and 3.6 s on Test 4 rather than only at the end, and that a level where
`complete` alone would blow the budget still returns the best incumbent instead of nothing.

## 6. Relevance pruning: measured, not shipped

The plan proposed excluding blocks that can never matter: start from `pending_blocks`,
flood-fill each relevant block's reachable anchors with walls and irrelevant blocks as
obstacles, and mark as relevant any block whose placement touches a reachable placement,
one step beyond it in any direction, or an exit shadow, to a fixpoint.

Measured on the five fixtures and five generated 12x12, 25-block, 4-wall levels
(`benchmarks/generate.py --seed 1 --count 5`): excluded 0 of 2, 8, 10, 14, 14 blocks on the
fixtures and 0 of 25 on every stress level. Every block in every sample is pending, because
each colour has a gate, and a pending block is relevant by definition. The preprocessing
would run on every level and prune on none of the ones we can see, so it was not added.

## 7. Bidirectional and meet-in-the-middle search: rejected

Backward search needs a well-defined goal set. Here the goal is "every pending block has
exited", but exited blocks leave no trace of where they went or in what order, and a
non-pending block can rest anywhere, so the goal side is a large set rather than a state.
Reversing a move is also one-to-many: a cascade of releases in the forward direction
corresponds to re-inserting any subset of exited blocks at any of their gate anchors. The
front-to-front matching that a meet-in-the-middle scheme relies on would have to compare
against that set. The engine's expansion cost is dominated by move generation and release
checks, and those would double.

## 8. Planning as SAT: rejected

A SAT encoding would add a solver dependency to a repo that currently needs only the
standard library at run time, and the horizon (49 moves on Test 4) with every intermediate
stop as a separate action gives thousands of action variables per step. The cascade rule
(release repeatedly until nothing more releases, with ice thresholds re-checked inside the
loop) and the shadow geometry for concave shapes are exactly the kind of fixpoint
semantics that are easy to encode subtly wrong, and an encoding bug would silently change
the meaning of `UNSOLVABLE`. The A* engine reuses the same simulator that the validator
replays solutions through, so there is one implementation of the rules.

## 9. Learned or stochastic heuristics: rejected

Simulated annealing, genetic search and learned policies can find solutions but cannot
prove their absence, and section 1 requires a sound `UNSOLVABLE`. They could only sit in the
guide slot of the anytime search, where quality is unverifiable without a benchmark set
far larger than five fixtures. Section 4 shows even the hand-written dependency term is a
win on one fixture and a loss on two; a learned term would face the same question with
behaviour that cannot be read and reasoned about.

## 10. A schedule change measured, then not shipped

The obvious next question after §5: do the middle phases of `SCHEDULE` — `(2.0, 2.0)` and
`(1.5, 1.5)` — earn their keep, or are they just overhead between `fast`'s starting point
and `complete`'s exact finish? Trimming to `(3.0, 3.0) -> (1.0, 0.0)` was measured, not
assumed, on both halves of the evidence.

On fixtures that finish before any deadline matters, it's a clean win: Test 5 drops from
34,115 to 26,927 expansions and 5.6s to 4.0s for the same 43-move answer; Test 3 similarly
improves with no change in the final move count. Cutting overhead that buys nothing was
exactly the right call there.

On a hard stress level that runs out of time before finishing, it isn't a win at all.
`stress_12x12_b25_s10`, 50s deadline: the full four-phase schedule reaches 88 moves at
44.8s; the trimmed schedule reaches only 93 moves at 36.7s — five moves worse, for a level
that never gets to the exact phase either way. The middle phases that look like pure
overhead when the search finishes anyway turn out to bank real, cheap incumbents before a
deadline cuts the search off, which is exactly the situation `auto` exists for. Trimming
helps the case that already finishes in a few seconds, comfortably inside the grading
limit regardless of schedule, and hurts the case the anytime design was built to survive.

Not shipped. Deadline-bound outcomes on hard levels are also genuinely noisy run to run —
which phase transition lands where depends on machine timing, not just the algorithm — so
a single comparison run isn't strong enough evidence to trade away quality on the harder
half of the distribution for a cosmetic speedup on the easier half.

## 11. Future work

- Multi-block additive pattern databases: blocked on the choice of abstraction, since two
  blocks on a 12x12 board already give ~20,000 abstract states per pair and the pairing has
  to be disjoint to stay admissible.
- Deferred heuristic evaluation in `fast`: blocked on the incremental estimate already
  making the admissible term nearly free; only the guide would be deferred, and it is the
  term that steers.
- Stubborn sets or other partial-order reduction over independent block moves: blocked on
  proving commutativity under cascades, where sliding one block can release another.
- Windowed plan repair between phases: blocked on measurement showing the exact phase
  does 95% of the work on Test 4, so there is little local repair could shortcut.

## 12. References

- Hart, Nilsson and Raphael (1968), A* and the admissibility argument.
- Pohl (1970), weighted A* (`f = g + w*h`).
- Likhachev, Gordon and Thrun (2003), ARA*: anytime search over a decreasing weight
  schedule with an INCONS list; the schedule here is the same idea, the INCONS list is
  unnecessary for the reason in section 5.
- Culberson and Schaeffer (1998), pattern databases; Korf and Felner (2002), disjoint
  additive pattern databases.
- Kautz and Selman (1992), planning as satisfiability.
- Valmari (1991), stubborn sets.
- Holte, Felner, Sharon and Sturtevant (2016), MM: meet-in-the-middle bidirectional search.
