import numpy as np

from apps import theremin as T
from apps.common.music import SCALES, midi_to_freq
from apps.common.synth import Oscillator
from tests.helpers import fake_hand, hand, moved


def test_mappings():
    assert T.y_to_midi(T.BOTTOM, 48, 2) == 48 and T.y_to_midi(T.TOP, 48, 2) == 72
    assert abs(T.midi_to_y(T.y_to_midi(0.5, 48, 2), 48, 2) - 0.5) < 1e-9
    assert T.y_to_volume(0.0) == 1 and T.y_to_volume(1.0) == 0


def test_hands_control_pitch_volume_and_mute():
    open_hand, fist = hand(1, 1, 1, 1, 1), hand(0, 0, 0, 0, 0)
    right = fake_hand(moved(open_hand, 0.3, -0.3))
    left = fake_hand(moved(open_hand, -0.3, 0.0))
    assert T.assign_hands([left, right]) == (right, left)
    assert T.assign_hands([left]) == (None, left)
    th = T.Theremin(Oscillator(), 48, 2, "livre", 0.7)
    th.update(right, None)
    assert th.volume == 0.7 and not th.muted and th.osc.target_amp > 0
    assert abs(th.osc.target_freq - midi_to_freq(T.y_to_midi(right.points[8][1], 48, 2))) < 1e-6
    th.update(fake_hand(moved(fist, 0.3, -0.3)), left)
    assert th.muted and th.osc.target_amp == 0
    th.scale, th.current_midi = "maior", None
    th.update(right, left)
    assert (th.current_midi - 48) % 12 in SCALES["maior"]
    img = np.zeros((720, 1280, 3), np.uint8)
    th.draw(img)
    assert img.any()
