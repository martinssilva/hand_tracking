import numpy as np

from apps import slice_game as S
from tests.helpers import fake_hand, hand, hand_with_index_at

W, H = 1280, 720


# ---------- geometria e fisica ----------
def test_segment_hits_circle():
    assert S.segment_hits_circle((0, 0), (100, 0), (50, 5), 10)        # atravessa
    assert S.segment_hits_circle((0, 0), (100, 0), (50, 10), 10)       # tangente
    assert not S.segment_hits_circle((0, 0), (100, 0), (50, 11), 10)   # passa por fora
    assert not S.segment_hits_circle((0, 0), (100, 0), (130, 0), 10)   # alem da ponta
    assert S.segment_hits_circle((5, 5), (5, 5), (8, 5), 4)            # segmento parado


def test_launch_reaches_apex_and_lands_on_target():
    g = S.GRAVITY * H
    vx, vy = S.launch_velocity(200, 600, 0.7 * H, g)
    f = S.Fruit(S.FRUITS[0], 200, H, vx, vy, 30)
    top, dt = f.y, 1 / 240
    while True:
        f.step(dt, g)
        top = min(top, f.y)
        if f.vy > 0 and f.y >= H:
            break
    assert abs((H - top) - 0.7 * H) < 5          # subiu o previsto
    assert abs(f.x - 600) < 5                    # caiu onde devia


# ---------- lamina ----------
def test_blade_needs_speed():
    slow, fast = S.Blade(), S.Blade()
    for i in range(5):
        slow.add(100 + i * 2, 300, i / 30, palm_px=100)    # 0,6 palma/s
        fast.add(100 + i * 40, 300, i / 30, palm_px=100)   # 12 palmas/s
    assert not slow.cutting and fast.cutting


def swipe(game, t0, y, x_from, x_to, frames=6, label="Right"):
    """Passa o indicador de x_from a x_to na altura y (pixels), um frame a cada 1/30s."""
    t = t0
    for i in range(frames):
        x = x_from + (x_to - x_from) * i / (frames - 1)
        game.process(t, [hand_with_index_at(x / W, y / H, label=label)], W, H)
        t += 1 / 30
    return t


def place(game, kind, x, y, owner=0):
    f = S.Fruit(kind, x, y, 0, 0, S.FRUIT_RADIUS * H * kind.size, owner=owner)
    game.fruits.append(f)
    return f


def playing_game(**kw):
    g = S.SliceGame(seed=1, **kw)
    g.start(0.0)
    for p in g.players:
        p.next_wave = 1e9        # sem lancamentos aleatorios nos testes
    return g


def test_fast_swipe_slices_and_slow_does_not():
    g = playing_game()
    place(g, S.FRUITS[0], 640, 300)
    g.speed = 0.0                                # congela a fisica para a fruta ficar parada
    swipe(g, 0.0, 300, 600, 680, frames=6)       # lento: ~1,5 palmas/s
    assert len(g.fruits) == 1 and g.players[0].board.score == 0
    swipe(g, 1.0, 300, 300, 1000, frames=6)      # rapido
    assert g.fruits == [] and g.players[0].board.score == 1
    halves = [p for p in g.pieces if p.kind == "half"]
    assert len(halves) == 2


def test_combo_bonus():
    g = playing_game()
    g.speed = 0.0
    for x in (400, 550, 700):
        place(g, S.FRUITS[1], x, 300)
    t = swipe(g, 0.0, 300, 300, 800, frames=6)
    p = g.players[0]
    assert p.sliced == 3 and p.board.score == 3
    g.process(t + 0.5, [], W, H)                 # fecha a janela do combo
    assert p.board.score == 3 + 3 and p.best_combo == 3


def test_bomb_and_missed_fruit_cost_lives_then_game_over():
    g = playing_game(lives=3)
    g.speed = 0.0
    place(g, S.BOMB, 640, 300)
    t = swipe(g, 0.0, 300, 300, 1000)
    assert g.players[0].board.lives == 2 and g.flash > 0
    g.speed = 1.0
    for _ in range(2):                           # duas frutas caem sem ser cortadas
        f = place(g, S.FRUITS[2], 640, H - 10)
        f.vy = 200
    for i in range(30):
        g.process(t + i / 30, [], W, H)
    assert g.state == S.GAME_OVER and g.players[0].board.lives == 0
    assert g.players[0].board.best == 0


def test_bomb_fatal():
    g = playing_game(lives=3, bomb_fatal=True)
    g.speed = 0.0
    place(g, S.BOMB, 640, 300)
    swipe(g, 0.0, 300, 300, 1000)
    assert g.state == S.GAME_OVER


def test_waves_get_bigger_and_include_bombs():
    g = S.SliceGame(seed=3)
    assert g._difficulty(0) == (2.4, 1, 0.0)
    interval, max_wave, bomb = g._difficulty(60)
    assert interval < 2.4 and max_wave == 5 and bomb > 0
    g.start(0.0)
    launched = 0
    t = 0.0
    while t < 20:                                # 20s sem jogador: ondas saem e frutas caem
        g.process(t, [], W, H)
        launched = max(launched, len(g.fruits))
        t += 1 / 30
    assert launched >= 1 and g.players[0].board.lives < 3


def test_start_with_open_hand_and_restart_delay():
    g = S.SliceGame(seed=1)
    open_hand = fake_hand(hand(1, 1, 1, 1, 1))
    g.process(0.0, [open_hand], W, H)
    g.process(0.5, [open_hand], W, H)
    assert g.state == S.START
    g.process(1.1, [open_hand], W, H)
    assert g.state == S.PLAYING
    g.state, g.ended_at = S.GAME_OVER, 2.0
    g.on_key(ord(" "), 2.5)
    assert g.state == S.GAME_OVER                # ainda dentro do RESTART_DELAY
    g.on_key(ord(" "), 4.0)
    assert g.state == S.PLAYING


def test_two_players_only_cut_their_side():
    g = playing_game(players=2)
    g.speed = 0.0
    left = place(g, S.FRUITS[0], 400, 300, owner=0)
    right = place(g, S.FRUITS[0], 900, 300, owner=1)
    # dedo no lado direito (jogador 2) passando por cima da fruta do jogador 2
    swipe(g, 0.0, 300, 700, 1200, label="Right")
    assert left in g.fruits and right not in g.fruits
    assert [p.board.score for p in g.players] == [0, 1]
    # fruta do jogador 1 so cai do lado dele
    for p in g.players:
        f = g._make_fruit(p, S.FRUITS[0])
        assert p.x1 <= f.x <= p.x2


def test_render_all_states():
    for players in (1, 2):
        g = playing_game(players=players)
        place(g, S.FRUITS[4], 300, 300)
        place(g, S.BOMB, 500, 300)
        g.speed = 0.0
        swipe(g, 0.0, 300, 200, 400)
        for state in (S.START, S.PLAYING, S.GAME_OVER):
            g.state = state
            img = np.full((H, W, 3), 70, np.uint8)
            g.draw(img, 5.0)
            assert img.any()
