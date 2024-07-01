import pytest

from geval import compute_weighted_score_over_probs


@pytest.mark.parametrize(
    "top_probs, expected_scores, expected_weighted_score",
    [
        (
            [("1", 0.2), ("2", 0.2), ("3", 0.2), ("4", 0.2), ("5", 0.2)],
            ["1", "2", "3", "4", "5"],
            3.0,
        ),
        (
            [("3", 0.3), ("4", 0.2), ("2", 0.2), ("5", 0.2), ("1", 0.1)],
            ["1", "2", "3", "4", "5"],
            3.2,
        ),
        (
            [("1", 0.1), ("2", 0.0), ("3", 0.0), ("4", 0.0), ("5", 0.0)],
            ["1", "2", "3", "4", "5"],
            1,
        ),
        (
            [("4", 0.1), ("5", 0.1), ("1", 0.0), ("2", 0.0), ("3", 0.0)],
            ["1", "2", "3", "4", "5"],
            4.5,
        ),
        (
            [("1", 0.4), ("a", 0.3), ("b", 0.2), ("c", 0.1), ("d", 0.1)],
            ["1", "2", "3", "4", "5"],
            1,
        ),
    ],
)
def test_compute_weighted_score_over_probs(
    top_probs, expected_scores, expected_weighted_score
):
    assert compute_weighted_score_over_probs(
        top_probs, expected_scores
    ) == pytest.approx(expected_weighted_score)
