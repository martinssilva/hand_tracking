import numpy as np

from apps.gesture_game import FEEDBACK, GAME_OVER, ROUND, START, GestureGame
from tests.helpers import fake_hand, hand


def test_full_game_flow():
    g = GestureGame(10, 5, 3)
    g.update(0.0, {"aberta"})
    assert g.state == START
    g.update(1.1, {"aberta"})                      # mao aberta 1s comeca
    assert g.state == ROUND
    target = g.target.key
    g.update(1.2, {target})
    g.update(1.7, {target})                        # segurou o gesto certo
    assert g.state == FEEDBACK and g.board.score == 10
    g.update(3.0, set())
    assert g.state == ROUND
    t = 3.0
    for _ in range(3):                             # 3 erros por tempo esgotado
        t += g.round_time() + 0.1
        g.update(t, set())
        assert g.state == FEEDBACK
        t += 1.3
        g.update(t, set())
    assert g.state == GAME_OVER and g.board.lives == 0 and g.board.best == 10


def test_process_uses_hands_and_space_restarts():
    g = GestureGame(10, 5, 3)
    g.process(0.0, [fake_hand(hand(1, 1, 1, 1, 1))], 1280, 720)
    assert g.detected_names == ["Mao aberta"]
    g.on_key(ord(" "), 0.5)
    assert g.state == ROUND and g.show_landmarks
    img = np.zeros((720, 1280, 3), np.uint8)
    g.draw(img, 0.6)
    assert img.any()
