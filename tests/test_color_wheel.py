import numpy as np

from apps import color_wheel as C
from apps.common.music import chord_name
from apps.common.synth import PolySynth
from tests.helpers import fake_hand, hand

W, H = 1280, 720
LAYOUT = C.WheelLayout(W, H, 2)


def test_every_cell_center_maps_back():
    for ring in range(2):
        for pos in range(12):
            assert LAYOUT.cell_at(*LAYOUT.label_pos(pos, ring)) == (pos, ring)
    assert LAYOUT.cell_at(W / 2, H / 2) is None
    assert LAYOUT.cell_at(W / 2, H / 2 - LAYOUT.r_in - 5) == (0, 0)   # topo = posicao 0


def at_cell(pos, ring, pinch=True, label="Right"):
    """Mao com o ponto de toque (pinca ou indicador) no centro da fatia."""
    lx, ly = LAYOUT.label_pos(pos, ring)
    pts = hand(0, 1, 1, 1, 1, ok=True) if pinch else hand(1, 1, 1, 1, 1)
    mx, my = ((pts[4][0] + pts[8][0]) / 2, (pts[4][1] + pts[8][1]) / 2) if pinch else pts[8]
    return fake_hand([(x + lx / W - mx, y + ly / H - my) for x, y in pts], label)


def test_playing():
    synth = PolySynth()
    wh = C.ColorWheel(synth, "pinca", "cromatica", "nota", "livre", 0, 48, 2)
    wh.update([at_cell(0, 0, pinch=False)], W, H)
    assert wh.playing_midis() == []                                   # sem pinca = mudo
    wh.update([at_cell(0, 0)], W, H)
    assert wh.playing_midis() == [48]
    wh.update([at_cell(7, 1)], W, H)
    assert wh.playing_midis() == [67]                                 # arrastou: troca a nota
    wh.update([at_cell(7, 1), at_cell(4, 0, label="Left")], W, H)
    assert wh.playing_midis() == [52, 67]                             # duas maos
    wh.update([], W, H)
    assert wh.playing_midis() == [] and not any(synth._owner)
    wh.chord_mode, wh.scale = "diatonico", "maior"
    wh.update([at_cell(2, 0)], W, H)
    assert chord_name(wh.playing_midis()) == "Re menor"
    wh.release_all()
    wh.order, wh.chord_mode = "quintas", "nota"
    wh.update([at_cell(1, 0)], W, H)
    assert wh.playing_midis() == [55]                                 # quintas: Do, Sol...
    wh.release_all()
    wh.mode = "toque"
    wh.update([at_cell(3, 1, pinch=False)], W, H)
    assert len(wh.playing_midis()) == 1
    img = np.zeros((H, W, 3), np.uint8)
    wh.draw(img)
    assert img.any()
