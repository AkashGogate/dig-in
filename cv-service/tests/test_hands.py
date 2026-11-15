from cvsvc.ingredient.hands import HandTripTracker

FPS = 15


def run(tracker, pattern):
    """pattern: list of (seconds, hand_in)"""
    out, t = [], 0.0
    for secs, inside in pattern:
        for _ in range(int(secs * FPS)):
            t += 1 / FPS
            r = tracker.update(t, inside)
            if r:
                out.append(r)
    return out


def test_dwell_counts_once():
    assert len(run(HandTripTracker(), [(1, False), (1.5, True), (1, False)])) == 1


def test_pass_through_does_not_count():
    assert run(HandTripTracker(), [(1, False), (0.2, True), (1, False)]) == []


def test_brief_dropout_is_same_entry():
    trips = run(HandTripTracker(), [(0.5, True), (0.13, False), (0.8, True), (1, False)])
    assert len(trips) == 1


def test_two_separate_reaches_count_twice():
    trips = run(HandTripTracker(), [(0.6, True), (1.0, False), (0.6, True), (1, False)])
    assert len(trips) == 2
