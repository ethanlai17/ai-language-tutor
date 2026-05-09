def calculate_next_review(
    quality: int,
    repetitions: int,
    ease_factor: float,
    interval: int,
) -> tuple[int, float, int]:
    """SM-2 algorithm. quality: 0-5. Returns (new_interval, new_ease_factor, new_repetitions)."""
    if quality < 3:
        return 1, ease_factor, 0

    if repetitions == 0:
        new_interval = 1
    elif repetitions == 1:
        new_interval = 6
    else:
        new_interval = round(interval * ease_factor)

    new_ef = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_ef = max(1.3, new_ef)

    return new_interval, new_ef, repetitions + 1


# Maps user-facing rating (1-4) to SM-2 quality (0-5)
RATING_TO_QUALITY = {1: 1, 2: 2, 3: 4, 4: 5}
