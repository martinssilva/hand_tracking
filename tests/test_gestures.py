import pytest

from apps.common.gestures import classify
from tests.helpers import hand

CASES = {
    "punho": hand(0, 0, 0, 0, 0),
    "aberta": hand(1, 1, 1, 1, 1),
    "joinha": hand(1, 0, 0, 0, 0, thumb_up=True),
    "apontar": hand(0, 1, 0, 0, 0),
    "paz": hand(0, 1, 1, 0, 0),
    "tres": hand(0, 1, 1, 1, 0),
    "rock": hand(0, 1, 0, 0, 1),
    "hangloose": hand(1, 0, 0, 0, 1),
    "ok": hand(0, 1, 1, 1, 1, ok=True),
}


@pytest.mark.parametrize("key", CASES)
def test_classify(key):
    g = classify(CASES[key])
    assert g is not None and g.key == key
