"""
Maos sinteticas para testar sem camera e sem mediapipe.

`hand(...)` monta 21 pontos (x, y) normalizados de uma mao de pe, com cada dedo
esticado (True) ou dobrado (False). `fake_hand(...)` embrulha os pontos num
objeto parecido com `tracker.Hand` (atributos `points` e `label`).
"""
from types import SimpleNamespace


def hand(thumb, index, middle, ring, pinky, thumb_up=False, ok=False):
    p = [None] * 21
    p[0] = (0.5, 0.9)
    xs = [0.42, 0.48, 0.54, 0.60]
    for i, (ext, x) in enumerate(zip((index, middle, ring, pinky), xs)):
        b = 5 + 4 * i
        p[b] = (x, 0.7)
        if ext:
            p[b + 1], p[b + 2], p[b + 3] = (x, 0.6), (x, 0.55), (x, 0.5)
        else:
            p[b + 1], p[b + 2], p[b + 3] = (x, 0.63), (x, 0.68), (x, 0.73)
    p[1], p[2] = (0.42, 0.85), (0.38, 0.8)
    if thumb_up:
        p[3], p[4] = (0.37, 0.66), (0.36, 0.55)
    elif thumb:
        p[3], p[4] = (0.35, 0.75), (0.30, 0.70)
    else:
        p[3], p[4] = (0.41, 0.74), (0.47, 0.72)
    if ok:
        p[4] = (p[8][0] + 0.01, p[8][1] + 0.01)
    return p


def moved(points, dx, dy):
    return [(x + dx, y + dy) for x, y in points]


def fake_hand(points, label="Right"):
    return SimpleNamespace(points=list(points), label=label)


def hand_with_index_at(x, y, label="Right", **fingers):
    """Mao aberta (ou com os dedos pedidos) com a ponta do indicador em (x, y)."""
    shape = dict(thumb=1, index=1, middle=1, ring=1, pinky=1)
    shape.update(fingers)
    pts = hand(**shape)
    return fake_hand(moved(pts, x - pts[8][0], y - pts[8][1]), label)
