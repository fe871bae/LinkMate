from eval.metrics import AnswerScore, percentile, recall_at, reciprocal_rank, wilson_interval


def test_wilson_interval_is_known_value_and_clamped():
    low, high = wilson_interval(9, 10)
    assert round(low, 3) == 0.596 and round(high, 3) == 0.982
    assert wilson_interval(0, 0) == (0.0, 0.0)
    assert wilson_interval(5, 5)[1] == 1.0


def test_percentile_interpolates():
    assert percentile([1, 2, 3, 4], 0.5) == 2.5
    assert percentile([], 0.5) == 0.0


def test_ranking_metrics():
    assert reciprocal_rank(["a", "b"], {"b"}) == 0.5
    assert reciprocal_rank(["a"], {"z"}) == 0.0
    assert recall_at(["a", "b", "c"], {"c"}, 3) and not recall_at(["a", "b", "c"], {"c"}, 2)


def test_answer_score_separates_acceptable_wrong_and_refusal():
    score = AnswerScore()
    assert score.add(["a", "acc", "bad"], {"a"}, {"acc"})
    assert not score.add(["acc"], {"a"}, {"acc"})
    assert score.add([], set(), set())
    assert not score.add(["bad"], set(), set())
    assert (score.hits, score.answerable, score.refusals, score.none) == (1, 2, 1, 2)
    assert (score.wrong_recommended, score.total_recommended) == (2, 5)
    assert score.balanced == 0.5
