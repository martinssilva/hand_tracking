import numpy as np

from apps.common.game import HoldTimer, Scoreboard, draw_game_over, draw_hud, draw_start_screen


def test_scoreboard():
    b = Scoreboard(3)
    b.add(5)
    b.lose_life()
    assert (b.score, b.lives, b.alive) == (5, 2, True)
    b.lose_life(); b.lose_life(); b.lose_life()
    assert b.lives == 0 and not b.alive
    b.finish()
    b.reset()
    assert (b.score, b.lives, b.best) == (0, 3, 5)


def test_hold_timer_accepts_time_zero():
    t = HoldTimer()
    assert t.update(0.0, True) == 0.0 and t.active   # 0.0 e um tempo valido
    assert t.update(1.5, True) == 1.5
    assert t.update(2.0, False) == 0.0 and not t.active


def test_screens_render():
    img = np.zeros((720, 1280, 3), np.uint8)
    draw_hud(img, Scoreboard(3))
    draw_start_screen(img, "T", ["a", "b"], "c", 0.5, 10)
    draw_game_over(img, 3, "x")
    assert img.any()
