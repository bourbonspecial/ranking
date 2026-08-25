# Boulder Ranking

Ranking engine for boulder problems 8C and harder, built from pairwise
"which was harder for you?" comparisons. See [SCOPE.md](SCOPE.md).

## Phase 1: rating engine

```
uv venv -p 3.12 && uv pip install -e ".[dev]"
.venv/bin/pytest
.venv/bin/ranking simulate --problems 120 --climbers 40 --seed 0
.venv/bin/ranking rank problems.csv comparisons.csv --algo bradley_terry
```

### Algorithms (`ranking/`)

| module | what |
|---|---|
| `bradley_terry.py` | **Default.** Bradley–Terry with ties (Davidson) fitted by MAP to all comparisons at once, with a Normal prior centred on the grade seed. Reports rating + uncertainty (Laplace). Order-independent. |
| `elo.py` | Sequential Elo replayed chronologically from the grade seeds. Ties = 0.5. |
| `winrate.py` | Naive share of comparisons "won". Sanity check only. |
| `personal.py` | Bradley–Terry fitted to one climber's own comparisons — the private "your ranking" view. |
| `pairs.py` | Compare-flow queue: unanswered pairs, rarest problems first. Ranking gate threshold `min(10, possible pairs)`. |
| `models.py` | `Problem`, `Comparison`, `Verdict`; `latest_comparisons()` keeps one answer per climber-pair. |
| `simulate.py` | Synthetic world with hidden true difficulties, mis-graded problems, biased climbers. Used to tune and test. |

Ratings are on an Elo-like scale (400 points = 10:1 odds). Seeds:
8C 1500 · 8C+ 1750 · 9A 2000 · 9A+ 2250.

### Prior strength (tuned on the simulator)

Spearman correlation with the hidden true order, mean over 8 seeds, 100
problems, 40 climbers:

| | grades only | Elo k=32 | BT sd=50 | **BT sd=100** | BT sd=200 | BT sd=400 | BT no prior |
|---|---|---|---|---|---|---|---|
| accurate grades, all pairs answered | 0.855 | 0.946 | 0.958 | **0.951** | 0.918 | 0.898 | 0.926 |
| accurate grades, 30% of pairs | 0.855 | 0.949 | 0.947 | **0.951** | 0.935 | 0.895 | 0.893 |
| noisy grades, all pairs | 0.740 | 0.910 | 0.913 | **0.917** | 0.896 | 0.881 | 0.917 |
| noisy grades, 30% of pairs | 0.740 | 0.909 | 0.878 | **0.909** | 0.901 | 0.873 | 0.885 |

`prior_sd=100` is the default. Medium priors (200–1000) do worst: they let a
handful of noisy comparisons drag sparsely-compared problems a long way
without either the grade or the data anchoring them.
