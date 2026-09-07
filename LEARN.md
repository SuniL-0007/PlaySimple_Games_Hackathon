# LEARN.md — Color Block Crush, end to end

This is the study version of the project: what each piece does, the decision behind it, and
the alternative that was considered and rejected. `DESIGN.md` is the short write-up for a
grader; `TRADEOFFS.md` is the algorithm-choice argument; this file is both, expanded, plus
every "why not X" an interviewer is likely to ask, plus a real bug story from this session.

---

## 1. The problem, precisely

Colored blocks sit on a `width x height` grid. A block slides in a straight line until it
hits a wall or another block — it does not stop early. A block exits only through a gate of
its own color on the border, and only if two extra conditions hold:

- **Ice** (`ic=N`): the block cannot exit until at least `N` *other* blocks have already
  exited. Checked against a live counter, not a snapshot.
- **Axis** (`ar=h` / `ar=v`): the block may only ever slide along one axis, so it can only
  approach a gate whose side matches that axis.

The puzzle is solved when every block that *has* a matching gate has exited (a block whose
color has no gate is inert scenery, never a goal condition — this distinction matters later,
in the bidirectional-search rejection).

The trap: exiting is a **cascade**. Placing one block can put a second block's own exit path
in the clear, and releasing that second block can clear a third. This has to be resolved as
a fixpoint — repeat "release anything now eligible" until nothing changes — not as a single
before/after check, and ice thresholds have to be re-read *inside* that loop because the
threshold itself moves as blocks exit mid-cascade.

---

## 2. Representation decisions

### 2.1 Bitboards, not coordinate sets

Every block shape and the wall layout are Python integers (`core/model.py: cells_mask`,
`shape_mask`). A cell is a bit; a placement is a mask; collision is `mask & obstacles`;
union is `|`. This is the standard trick for small fixed-size grids (chess engines,
Sokoban/Rush-Hour solvers) and it matters here because collision checks run on every single
generated move — millions of times on the harder fixtures — so it has to be one machine
instruction, not a set-intersection.

**Precomputed per block, once, at level-build time**, not recomputed per move:

- `masks[block][anchor]` — the placement bitmask at that anchor.
- `steps[block][direction][anchor]` — the next anchor one cell over, or `-1` at the edge.
  A slide is a `while` loop walking this table, not re-deriving geometry.
- `exit_shadows[block][anchor]` — `None` unless the block is color-matched to some gate,
  fits that gate's span, and (if axis-restricted) is on the allowed axis; otherwise the
  cells that must stay empty between the block and the edge. `shadow_mask` in
  `core/model.py` builds this per-column (top/bottom gates) or per-row (left/right gates)
  to handle **concave shapes correctly** — an L-shaped block like `RA_BL` needs a
  different empty-cell requirement per column of its own footprint, not one bounding-box
  check.

### 2.2 The tag-cell gotcha

A block's printed anchor is its **row-major-first occupied cell**, not its bounding-box
corner — `Block.tag_offset` is `min(cells, key=lambda c: (c[1], c[0]))`. These differ for a
shape like `RA_BR` (Test 4's block `C`: cells `(1,1) (0,2) (1,2)`) — the tag is `(1,1)`, the
bbox corner is `(0,1)`, a cell the block doesn't even occupy. Missing this would silently
produce move coordinates that don't match the grader's expected notation while still *look*
plausible — the kind of bug that survives a casual read and fails a diff.

### 2.3 State = `(anchors: bytes, exit_mask: int)`

One anchor per block (or the sentinel `width*height` once exited), plus a bitmask of which
blocks have exited. `bytes` instead of a tuple of ints: smaller per-state memory (matters at
2.5M stored states) and faster to hash — both measured, not assumed, before committing to it
over the more obvious tuple.

### 2.4 Interchangeable blocks collapse into one key

Test 4 has four identical `DB 1x1` blocks; Test 5 has eight identical `Y 1x1` blocks — same
color, cells, ice, axis (`Block.interchangeability`). Left alone, the search would treat
"blocks 3 and 7 swapped positions" as a *different state* from the identical-looking
original, multiplying the reachable space by `4!` / `8!` for no reason — the puzzle doesn't
care which physical copy is where. `core/model.py: group_spans` records each such group's
contiguous index range at build time; `core/state.py: canonical_key` sorts each group's byte
slice before using it as the closed-set key, so all `k!` permutations of one group collapse
to one entry. `search/astar.py` special-cases the 2-element-group case (`first, second =
...; if first > second: swap`) instead of calling `sorted()` — cheap, and it is the common
case (pairs), so it's worth the branch.

### 2.5 Why this isn't premature optimization

Every one of the above was adopted because a fixture *demanded* it, not speculatively:
tag-cell came from Test 4 failing a coordinate check; interchangeable-group collapsing came
from Test 4/5's reachable-state counts being untenable without it; bitboards came from move
generation being the measured hot path. Nothing here is "might need this later."

---

## 3. Move generation (`core/moves.py`)

`legal_moves` slides every unfrozen, unexited block (`ice_thresholds[block] > exits`
excludes it) along its `allowed_directions`, and **yields every intermediate stop, not just
the farthest one**. This is a real correctness requirement, not caution: some fixture
solutions use a *partial* slide — stopping a block halfway matters because full-distance-only
generation would make some genuinely solvable levels look unsolvable. All of one block's
moves come out of the generator contiguously (fixed outer loop over `enumerate(anchors)`) —
`search/astar.py`'s incremental key-patching logic depends on this ordering to know when it
has moved on to a new block.

---

## 4. The simulator (`core/simulator.py`)

`apply_move` places a block, then `release_exiting_blocks` runs the cascade fixpoint:
recompute occupancy once, then loop over exit-candidates repeatedly, releasing any block
whose shadow is clear **and** whose ice threshold is now met, until a full pass releases
nothing. The threshold re-check has to be *inside* the loop: in Test 5, block `9` (`ic=1`)
already sits on its own gate at the start, but can't leave until block `A` exits — which
happens in the *same* cascade, since `A` exiting is what raises the count to 1. A
before/after check (snapshot the exit count, check once) would strand block `9` and report
the level unsolvable when it isn't.

`core/validator.py: validate_solution` replays every move of a candidate solution through
this exact simulator — legality checked via `legal_moves`, cascade via `apply_move` — before
`solve.py` ever prints it. This is the single point that makes "the printed answer is wrong"
structurally impossible: whatever the search engine computed, the thing that reaches stdout
passed through the same rules module a human-written solution would have to satisfy.

---

## 5. The search engine (`search/astar.py`)

### 5.1 Reopening instead of a CLOSED set

There is no closed set — only `best_depth: dict[key, int]`. A popped node whose depth is
worse than the recorded best for its key is discarded; a child that improves on the recorded
depth for its key is pushed again, even if that key was already expanded. Under a consistent
heuristic this costs nothing (no node is ever *reached* more cheaply after being expanded),
and it is what let the anytime engine (§6.3) skip ARA*'s usual INCONS bookkeeping entirely —
see that section for why.

### 5.2 Incremental key and heuristic updates

Two independent constant-factor optimizations, each verified safe by checking that expanded/
generated counts didn't change after adding them (i.e., they change performance, not
behavior):

- **Key**: instead of calling `canonical_key` (allocate + rebuild + sort) for every
  generated child, `expand()` keeps a `bytearray` scratch buffer seeded from the parent's
  key and patches only the one byte (or the one interchangeable group) that actually moved.
  Falls back to a full rebuild whenever a cascade fires (`child_mask != exit_mask`), since a
  cascade can move several blocks to the exit sentinel at once.
- **Heuristic**: `heuristics/distance.py: contributions` hands back a per-block, per-anchor
  table. Since the admissible heuristic is a *sum of independent per-block terms*, moving
  one block changes the total by exactly `shares[new_anchor] - shares[old_anchor]` — no
  cascade means no need to resum every pending block from scratch. This only works because
  the heuristic is additive across blocks; it would be unsound to apply the same trick to a
  heuristic with cross-block interaction terms (a reason multi-block pattern databases,
  §7.8, need a different incremental strategy or none at all).

### 5.3 Dual-estimate priority and the anytime schedule

`BestFirstSearch` tracks two numbers per node: `h_adm` (always the admissible distance
estimate) and `h_guide` (an optional, inadmissible steering term). Priority is
`depth + weight*h_adm + guide_weight*h_guide`. Pruning — at push, at pop, and when
rebuilding the open list — checks `depth + h_adm >= bound` **only**; `h_guide` never
participates in a correctness-relevant decision, only in ordering. This split is what lets
one engine implement all three solvers:

| Solver | weight | guide_weight | phases |
|---|---|---|---|
| `complete` | 1.0 | 0.0 | one, exact |
| `fast` | 3.0 | 3.0 | one, weighted |
| `auto` | schedule `(3,3)→(2,2)→(1.5,1.5)→(1,0)` | — | four, anytime |

A goal popped while `weight==1 and guide_weight==0` returns immediately — that is a
certified-optimal answer, because at that setting priority is exactly `depth + h_adm` and
the heuristic is consistent. A goal popped during any other phase becomes an **incumbent**:
record it, tighten `bound` to its depth, and — if the anytime driver has another phase
queued — `retarget()` the open list to the next `(weight, guide_weight)` and keep searching
instead of returning. `retarget` rebuilds `self.open` from the surviving entries (still at
their recorded best depth, still under the new bound), recomputing each one's priority and
lazily computing `h_guide` only for entries that need it and didn't have it yet.

**One deliberate deviation from the textbook description**: a goal found in a weighted phase
returns immediately if there is *no further phase to refine into* — this is what makes
`fast` (a single weighted phase, by construction) return at its first solution instead of
searching to exhaustion for no reason. Read literally, "never return during a weighted
phase" would make `fast` slower for zero benefit, since it has nowhere left to refine to.

---

## 6. The three solvers, in depth

### 6.1 `complete` — provably optimal

Heuristic: `heuristics/distance.py: slide_distances` runs one backward, multi-source BFS per
block, starting from all of that block's exit anchors, over a board that contains **only
walls** (every other block is treated as if it weren't there). The result is the minimum
number of slides that block would need if it had the whole board to itself. Summing this
over every still-pending block is:

- **Admissible** — it can never overestimate the true cost, because a real move slides one
  real block and reduces that one block's *relaxed* distance by at most 1 (removing
  obstacles the relaxed version never had can only help, never hurt, the true cost).
- **Consistent** — `h(parent) <= cost(edge) + h(child)` holds for the same reason, edge by
  edge, which is exactly what makes the first goal popped at weight 1 optimal *without*
  reopening a state after it's expanded.

This is, honestly, a **degenerate one-block pattern database**: an exact-cost lookup table
built once per block over an abstracted (walls-only) version of the board. It is cheap
precisely because it never has to reason about two blocks at once — which is also its
weakness (§7.8).

### 6.2 `fast` — deliberately greedy, with a hand-built guide

`fast` adds `heuristics/combined.py: guide` — `DEPENDENCY_WEIGHT * dependency_penalty +
FROZEN_PENALTY * frozen_count` — at `weight=3, guide_weight=3`.

`dependency_penalty` (`heuristics/dependency.py`) is the actual novelty: for every pending
block, `blockers_of` looks at the corridor (`heuristics/blocking.py: corridors` — an
L-shaped or straight sweep from the block's current anchor to its nearest exit, computed via
`swept_cells`) and finds which *other* blocks currently sit inside it, picking whichever of
the horizontal/vertical corridor has **fewer** obstructions (`min(candidates, key=len)`).
Then, **one level deeper**: for each of those direct blockers, how many blockers do *they*
have in their own corridor? Depth is capped at 2 and each term at `BLOCKER_CAP=4` — a
straight count of "how tangled is this" rather than a full recursive plan, on purpose, so
the heuristic stays O(blocks) instead of exploring the interaction graph exhaustively.

`frozen_count` adds one point per pending block still ice-gated above the current exit
count — a block that literally cannot move yet is worth flagging separately from one that's
merely far away.

Effect, measured directly (not assumed): the guide is a **large, one-fixture win**. On Test 4
it's the difference between 259,396 expansions (distance alone, weight 3, still finds it) —
wait, precisely: distance-only at weight 3 expands 253,367 states in 17.8s; adding the guide
drops that to 5,807 expansions in ~4s. But the same guide **costs** moves and wall time on
Test 3 (183 expansions guide-less vs. 327 with it) and Test 5 (16,903 vs. 11,439) — each
guide evaluation costs more than the search time it saves when the level isn't actually
tangled. `TRADEOFFS.md` §4 has the full numbers; the honest conclusion is that this guide is
a targeted fix for one failure mode (blocking chains), not a universal accelerant.

### 6.3 `auto` — the anytime hybrid

The old `auto` ran `fast` for up to 10s, then started `complete` from scratch, discarding
`fast`'s entire search tree. The new one is a single `BestFirstSearch` run through the
schedule in §5.3, keeping `best_depth` and the parent/move arrays across every phase.

**Why no INCONS list (the standard ARA* bookkeeping) is needed here**: ARA* needs an INCONS
list because it uses a CLOSED set and has to *defer* reopening a node mid-iteration to avoid
reprocessing it immediately. This engine never had a CLOSED set (§5.1) — a cheaper path to
an already-expanded state is simply re-pushed, which is exactly the operation an INCONS list
exists to schedule for later. With reopening happening unconditionally, there's nothing left
for INCONS to defer.

**What's actually certified**: any goal popped while `weight==1, guide_weight==0` is optimal
by the standard A* argument. More than that — an **emptied open list with an incumbent
present certifies that incumbent as optimal at any weight**, because bound-pruning uses only
the admissible term: any state on a strictly cheaper path would satisfy `depth + h_adm <
bound`, so it could not have been pruned, could not have been marked stale, and could not
have had an infinite estimate — it would still be sitting in the open list. If the open list
is empty, no such state exists. This is why `auto` reports `optimal=True` on every one of the
five fixtures even though the schedule technically ends at weight 1 anyway; the more
interesting case is a small level where the open list would empty out *before* the schedule
reaches weight 1 — optimal proven early, for free.

**Measured trade-off**: on fixtures where `complete` was already fast, the weighted warm-up
phases add real overhead — Test 5 goes from `complete`'s 0.95s to `auto`'s 5.68s, because the
bound from an early, mediocre incumbent (53 moves) barely prunes an exact search whose
frontier never exceeds 43. On the levels this was actually built for — hard synthetic
12x12/25-block boards where `complete` hits its 2.5M-state cap 100% of the time (0/20
solved) — `auto` matches `fast`'s solvability exactly (same 14/20) and beats its move count
on every one of those 14, by 1 to 11 moves. It is not a strict win everywhere; it is a
deliberate trade of typical-case speed for worst-case survivability, and both halves of that
trade are measured, not asserted.

---

## 7. Algorithms considered and rejected — the full interview list

The project's ordering, stated once and applied consistently everywhere below:
**correctness (a sound `UNSOLVABLE`, a valid replayed solution) beats speed, and speed beats
move count.** Every rejection below is a rejection *against that ordering*, not a vague
"seemed too fancy."

### 7.1 Beam search

Keep only the best `K` nodes per depth layer, discard the rest permanently. Attractive on
paper because it bounds memory to `O(K * depth)` — exactly the resource `complete` runs out
of on hard boards (§8). Rejected: beam search is **neither complete nor optimal**. If every
one of the `K` survivors at some layer sits on a path that later dead-ends (a state can look
great by relaxed distance and then be one slide from wedged against a wall with no legal
continuation), the correct path is gone forever — no backtracking, no reopening. On a puzzle
where the contract requires a *sound* `UNSOLVABLE`, that failure mode is silent and
catastrophic: a genuinely solvable level would come back with no answer, indistinguishable
from an actually-unsolvable one. This engine already has an honest way to spend a bounded
memory budget — `MAX_STORED_STATES` returning the best incumbent (or a plain `TIMEOUT`)
instead of crashing — which degrades loudly instead of lying. Beam search trades that honest
degradation for a silent one; not a trade worth making here.

### 7.2 Plain DFS

Would eventually find *a* path (if cycle-protected — the state graph does have real cycles,
since sliding a block out and back is a legal, reversible move pair) but has no notion of
move-count quality: depth-first commits to the first branch it sees and will happily explore
a 10,000-move detour before backtracking to try the 2-move solution. Since the puzzle is
graded on move count as well as correctness, DFS optimizes for neither of the two things
that matter after correctness. Not used anywhere, not even as a baseline (BFS fills that
role better, §7.4).

### 7.3 Iterative-deepening DFS (IDDFS)

The standard fix for DFS's optimality problem: search depth-limited DFS, and increase the
limit by one each round until a goal appears, giving BFS's move-count guarantee at DFS's
`O(depth)` memory instead of BFS's `O(branching^depth)`. Its entire value proposition is "you
have no heuristic and branching is too wide for BFS's memory." That's not this situation —
there already is a strong, cheap, admissible heuristic, which makes the strictly better
version of this idea IDA* (§7.5), not plain IDDFS.

### 7.4 Plain BFS / Dijkstra — kept, not rejected

`search/bfs.py` exists on purpose, as a **baseline**, not a candidate for `--solver auto`.
Every move here costs 1, so Dijkstra and BFS are the same algorithm in this domain. It
solves the trivial fixture (Test 1) instantly and times out on everything past it — that
result is the actual evidence, cited in `DESIGN.md`, that the admissible heuristic is doing
real work and isn't just overhead. Keeping a deliberately weak baseline around to *prove* a
design choice earns its keep is different from keeping a superseded implementation "just in
case."

### 7.5 IDA*

The natural memory-bounded version of A*, and directly relevant since `complete` genuinely
does hit `MAX_STORED_STATES` on hard boards. Rejected for now for two domain-specific
reasons, not a generic "IDA* is old-fashioned":

1. IDA* has no memoization across iterations by design — no closed set, no transposition
   table. This throws away the single biggest lever this project has on the state count:
   interchangeable-group canonicalization (§2.4). Rebuilding that benefit inside IDA* means
   adding a transposition table back in, at which point it isn't really IDA* anymore, it's
   A* with a size-bounded closed set — a different, also-reasonable idea, but not free.
2. IDA*'s classic wins (15-puzzle, Rubik's cube) come from *huge branching with near-zero
   per-node cost*. Here, per-node cost is not near-zero: move generation yields every
   intermediate stop of every slide, and `fast`'s guide heuristic runs a corridor sweep per
   candidate block. Re-deriving the same nodes across repeated iterations multiplies a
   comparatively expensive operation rather than a cheap one — the trade IDA* is built to
   make looks worse here than in its usual home turf.

Listed as genuine future work if hidden grading levels turn out to hit the memory cap more
often than the time budget.

### 7.6 Greedy best-first (weight → infinity)

The limiting case of weighted A* as weight grows without bound: order purely by heuristic,
ignore `depth` entirely. `fast`'s weight of 3 is a deliberate, finite point on this spectrum,
not "as greedy as possible" — pure greedy search gives up A*'s bounded-suboptimality
guarantee entirely and is more prone to being led into a heuristic-flattering cul-de-sac with
no cost term to eventually outweigh a bad early choice. A finite weight keeps the visited
depth as a real, if discounted, vote in the ranking.

### 7.7 Bidirectional / meet-in-the-middle search

Search forward from the start and backward from the goal, hoping the two frontiers meet.
Rejected on two independent grounds specific to this simulator, not "hard in general":

- The goal is a **unique state** only when every block in the level is pending (has a
  matching gate) — true for the five fixtures, not guaranteed on a generated level where a
  color can end up with no gate at all (`benchmarks/generate.py` can and does produce this).
  Without a unique goal, backward search doesn't have a single state to start from — it has
  a large goal *set*, and the meet-in-the-middle matching has to account for that.
- Reversing a forward move is one-to-many where it matters most: reversing an **exit
  cascade** means choosing which subset of exited blocks to re-insert and in what order,
  since the forward direction can release several blocks in a single fixpoint pass. Getting
  this wrong doesn't just slow the search down — it risks a wrong `SOLVED`/`UNSOLVABLE`
  verdict, which this project's stated ordering (§7, opening line) rejects outright even at
  a large potential speed win.

### 7.8 Multi-block additive pattern databases — future work, not rejected

`complete`'s heuristic (§6.1) is a *single-block* pattern database. A real disjoint additive
PDB over pairs or triples of interacting blocks would be strictly stronger and still
admissible, and would directly attack the actual weakness measured in §6.1 (it can't see two
blocks blocking each other). Not attempted here because the abstraction has to stay
*disjoint* to remain admissible when summed — which means it has to interact correctly with
the same interchangeable-group canonicalization the rest of the engine leans on — and the
state-enumeration cost per candidate pairing competes directly with the same
`MAX_STORED_STATES` budget the exact solver is already straining. A serious next step, not a
quick one.

### 7.9 Planning as SAT

Encode "does a plan of length <= k exist" as a boolean formula, hand it to an off-the-shelf
SAT solver, increase `k` until SAT. Rejected: it requires a new solver dependency in a
project that currently needs nothing beyond the standard library, and the cascade fixpoint
plus ice-threshold semantics are exactly the kind of stateful, iterate-to-a-fixpoint logic
that is easy to encode subtly wrong in flat clauses — an encoding bug there would silently
redefine what `UNSOLVABLE` means, which is the one failure mode this whole design goes out of
its way to avoid.

### 7.10 Simulated annealing / genetic search / learned heuristics

All three can find a solution; none can *prove the absence of one*, and a sound
`UNSOLVABLE` is a hard requirement here, not a nice-to-have. A learned or stochastic term
could only ever occupy the inadmissible `guide` slot in the anytime engine — and §6.2 already
shows that even a small, fully-understood, hand-written guide term is a net win on one
fixture and a net loss on two others. A black-box term would raise the identical question
with no way to reason about *why* it wins or loses, on a project with exactly five labeled
fixtures to learn anything from.

### 7.11 Relevance-based move pruning — measured, then not shipped

The classical Rush-Hour-solver trick: fold any block that can *never* affect a pending
block's path into the walls, shrinking the branching factor directly rather than just
re-ordering the search. Before writing any pruning code, this was **measured**: a flood-fill
reachability closure was run over the five fixtures plus five generated 12x12/25-block
levels. Result: it excluded zero blocks, every single time, on every level tested — because
every block in every sample always had a matching gate, so every block started out
"relevant" by definition, and any-stop sliding on a dense board makes the reachable-closure
touch nearly the whole grid anyway. Writing the preprocessing step would have added real
complexity for a measured benefit of zero on every sample available. Documented in
`TRADEOFFS.md` §6 with the actual counts, not shipped.

### 7.12 Strong stubborn sets / partial-order reduction

The principled generalization of §7.11, from classical planning: identify which pairs of
moves are guaranteed to commute so the search can permanently commit to one ordering rather
than exploring all interleavings. Deferred, not rejected: the correctness of a stubborn-set
reduction rests on proving an interference relation, and this puzzle's forced-exit cascade
is a **conditional effect on every single move** (sliding block A can release block B, which
changes what's true after the move in a way that isn't visible just from A's own
destination) — breaking the clean commutativity argument stubborn sets are usually built on.
A correct interference relation under cascades is genuinely research-sized work, not a
quick win.

### 7.13 Deferred (lazy) heuristic evaluation in `fast`

A standard, low-risk speedup: evaluate the guide heuristic when a node is *popped*, not when
it's *generated* — since `fast` generates roughly 13x more children than it ever expands
(Test 4: 79,153 generated vs. 5,807 expanded), most guide evaluations are wasted work on
nodes that never get explored. Deferred, not because it's wrong, but because it changes
`fast`'s search order and therefore its exact move counts and expansion counts — which are
the frozen regression numbers every other change in this project has been checked against.
A real, low-risk win, intentionally not taken during a pass whose whole discipline was
"don't move the goalposts while proving the redesign didn't regress anything."

---

## 8. A real bug, found by testing honestly

Running all three solvers across 20 generated 12x12/25-block stress levels (not just the
five fixtures) surfaced a genuine timing defect that no amount of fixture testing would ever
have caught:

**Symptom**: `fast` on one generated level (`stress_12x12_b25_s15`) took **61.25 seconds**
against a stated 50-second budget — an 11-second overshoot, past even the assignment's noted
60-second hard grading limit.

**Root cause**: the deadline was checked once per **1024 expanded** nodes (`run()`'s outer
loop), but the dominant wall-clock cost is the guide heuristic, which runs once per
**generated** child inside `push()` — not per expansion. On a dense 25-block board with 100+
generated children per expansion, that's over 100,000 unchecked heuristic evaluations
possible inside a single gap between deadline checks. The mechanism pre-dates this session's
anytime redesign; it simply had never been exercised by a level dense enough to expose it
until this exact stress run.

**Fix**: check the deadline every 256 **generated** nodes (a count proportional to the
actual cost driver) instead of only every 1024 expanded, raising a `DeadlineExceeded`
signal from inside `expand()`'s loop that `run()` catches and turns into the same
`finish_interrupted()` path as before. Also trimmed `TOTAL_BUDGET_SECONDS` from 50 to 45 to
buy back margin under the external 60-second kill.

**Verification, not assertion**: re-ran the identical worst-case level after the fix — 45.12s
against a 45s budget, a 0.12s overshoot instead of 11.25s. Re-ran the full test suite (75
passing) and lint (clean) to confirm nothing else moved. One existing test had to be
rewritten (`test_auto_solver_returns_its_best_incumbent_when_the_deadline_expires`) because
it had accidentally encoded the *old, coarse* check's timing coincidence as if it were a
requirement — a good example of a test that passed for the wrong reason, caught by a
deliberate behavior change rather than a code review.

---

## 9. Testing and verification philosophy

- `core/validator.py` replays every printed solution through the real simulator before
  `solve.py` emits it — an incorrect move list is structurally prevented from reaching
  stdout, not just hoped against.
- Fast/complete's expanded/generated/move counts on all five fixtures are treated as a
  **frozen regression fingerprint**: every optimization in this project (incremental keys,
  incremental heuristics, the anytime refactor) was accepted only after confirming those
  exact counts didn't move — proof that the change is a constant-factor speedup, not an
  accidental behavior change wearing a performance-improvement costume.
- Claims in `TRADEOFFS.md` and this file are measured, not recalled — the relevance-pruning
  section exists because someone actually ran the flood-fill and counted, not because it
  "should" prune nothing.
- Stress-testing on synthetic hard levels (not just the five graded fixtures) is what found
  both real findings in this project: that `complete` hits its memory cap before its time
  budget on hard boards, and the deadline-overshoot bug in §8. Fixture-only testing would
  have shipped both.
- Not every measured optimization survives contact with harder evidence. Trimming `auto`'s
  weight schedule to two phases instead of four looked like a clean win on fixtures that
  finish before any deadline (Test 5: fewer expansions, less time, same 43 moves). On a
  hard stress level that runs out of time before finishing, the same trim came back five
  moves *worse* — the middle phases that look like pure overhead when the search finishes
  anyway were banking real incumbents before the deadline cut it off, which is exactly the
  situation `auto` exists for. `TRADEOFFS.md` §10 has the numbers. Not shipped, precisely
  because the evidence split by exactly the axis (deadline-bound vs. not) that mattered.

---

## 10. Benchmark numbers, for reference

| fixture | complete (moves / expanded / s) | fast (moves / expanded / s) | auto (moves / expanded / s) |
|---|---|---|---|
| test1 | 2 / 2 / 0.00 | 2 / 2 / 0.00 | 2 / 2 / 0.00 |
| test2 | 10 / 10 / 0.00 | 11 / 11 / 0.01 | 10 / 20 / 0.01 |
| test3 | 24 / 64,301 / 4.00 | 32 / 327 / 0.11 | 24 / 74,219 / 5.26 |
| test4 | 49 / 259,396 / 19.53 | 58 / 5,807 / 4.10 | 49 / 264,675 / 21.15 |
| test5 | 43 / 16,312 / 0.95 | 53 / 11,439 / 3.02 | 43 / 34,115 / 5.68 |

20 generated 12x12 / 25-block stress levels, 45s budget: `complete` solved **0 / 20**
(memory-cap `TIMEOUT` every time); `fast` and `auto` solved the same **14 / 20**; `auto`
beat `fast`'s move count on all 14 (deltas from -1 to -11 moves).

---

## 11. Interview cheat sheet

**"Walk me through the architecture."** Bitboards for O(1) collision, precomputed
per-block move/shadow tables so the hot loop is table lookups, `(anchors, exit_mask)` as the
whole state, canonical keys that sort interchangeable-group slices to avoid counting
permutations of identical blocks as distinct states.

**"Why A* and not X?"** Have §7 ready verbatim for beam search, DFS/IDDFS, IDA*,
bidirectional, SAT, and learned heuristics — each has a one-sentence, domain-specific reason,
not a generic "A* is standard."

**"How do you know your heuristic is admissible?"** Per-block relaxed distance via backward
BFS on a walls-only board; a real move can reduce one block's relaxed distance by at most 1,
so the sum can't overestimate. Consistency follows the same argument edge-by-edge.

**"What's the actual novel part?"** The anytime engine needing no INCONS list, because this
engine never had a CLOSED set to begin with — reopening already does what INCONS exists to
defer. Second: the dependency-aware guide heuristic, and the honest admission (measured, not
hidden) that it's a net loss on two of the three hard fixtures and a big win on the third.

**"Tell me about a bug you found."** §8, verbatim — found by stress-testing beyond the
graded fixtures, root-caused to a mismatch between what triggers a check (`expanded` count)
and what actually drives the cost (`generated` count and heuristic evaluations), fixed, and
re-verified against the exact case that exposed it.

**"What would you do next?"** Multi-block pattern databases (§7.8) for a strictly stronger
`complete` heuristic, and IDA* or a size-bounded closed set (§7.5) if hidden levels turn out
to hit the memory cap more often than the time budget in practice.

**"What's the actual trade-off in your design?"** `auto` trades typical-case wall time
(worse than `complete` alone when `complete` was already fast — measured, not hidden) for
worst-case survivability (matches `fast`'s solvability and beats its move count on every
hard level in a 20-level stress sample where `complete` never once finishes). Both halves of
that trade are numbers in this file, not claims.
