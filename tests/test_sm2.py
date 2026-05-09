import pytest
from core.sm2 import calculate_next_review, RATING_TO_QUALITY


def test_first_rep_success():
    interval, ef, reps = calculate_next_review(5, 0, 2.5, 1)
    assert interval == 1
    assert reps == 1
    assert ef > 2.5


def test_second_rep_success():
    _, ef, _ = calculate_next_review(5, 0, 2.5, 1)
    interval, ef2, reps = calculate_next_review(5, 1, ef, 1)
    assert interval == 6
    assert reps == 2


def test_third_rep_uses_ef():
    _, ef, _ = calculate_next_review(4, 1, 2.5, 1)
    interval, _, reps = calculate_next_review(4, 2, ef, 6)
    assert interval == round(6 * ef)
    assert reps == 3


def test_failure_resets():
    interval, ef, reps = calculate_next_review(1, 5, 2.5, 20)
    assert interval == 1
    assert reps == 0
    assert ef == 2.5  # EF unchanged on failure


def test_ef_clamped_to_minimum():
    interval, ef, reps = calculate_next_review(0, 3, 1.4, 10)
    assert ef >= 1.3


def test_quality_below_3_is_failure():
    for q in (0, 1, 2):
        i, _, r = calculate_next_review(q, 5, 2.5, 30)
        assert i == 1 and r == 0, f"quality {q} should reset"


def test_rating_map_covers_all_user_ratings():
    assert set(RATING_TO_QUALITY.keys()) == {1, 2, 3, 4}
    for q in RATING_TO_QUALITY.values():
        assert 0 <= q <= 5
