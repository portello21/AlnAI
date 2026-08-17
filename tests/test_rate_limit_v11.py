from core.rate_limit import SlidingWindowRateLimiter


def test_sliding_window_rate_limit_recovers_after_window():
    limiter = SlidingWindowRateLimiter(2, 10)
    assert limiter.allow("user", now=1) == (True, 1)
    assert limiter.allow("user", now=2) == (True, 0)
    assert limiter.allow("user", now=3) == (False, 0)
    assert limiter.allow("user", now=12) == (True, 1)


def test_rate_limit_fails_closed_without_identity():
    assert SlidingWindowRateLimiter(2).allow("")[0] is False
