"""End-to-end: the algorithms must recover the hidden true order better than the grades alone."""
from ranking import fit_bradley_terry, replay_elo, latest_comparisons, grade_to_rating
from ranking.simulate import SimConfig, simulate, spearman


def test_algorithms_beat_grade_seed():
    world = simulate(SimConfig(n_problems=80, n_climbers=40, seed=3))
    truth = world.true_order()
    comps = latest_comparisons(world.comparisons)
    seed_order = [p.id for p in sorted(world.problems, key=lambda p: -grade_to_rating(p.seed_grade))]
    base = spearman(truth, seed_order)
    bt = spearman(truth, fit_bradley_terry(world.problems, comps).order())
    elo = spearman(truth, replay_elo(world.problems, comps).order())
    assert bt > base + 0.05
    assert elo > base
    assert bt >= elo - 0.02  # BT should be roughly as good as Elo or better


def test_bt_is_order_independent():
    world = simulate(SimConfig(n_problems=40, n_climbers=20, seed=5))
    comps = latest_comparisons(world.comparisons)
    a = fit_bradley_terry(world.problems, comps).order()
    b = fit_bradley_terry(world.problems, list(reversed(comps))).order()
    assert a == b
