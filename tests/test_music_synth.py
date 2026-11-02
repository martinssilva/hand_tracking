import math

import numpy as np

from apps.common.music import (SCALES, chord_name, freq_to_midi, midi_to_freq, note_name,
                               parse_note, snap_to_scale, triad)
from apps.common.synth import SAMPLE_RATE, WAVES, Oscillator, PolySynth


def test_notes():
    assert parse_note("A4") == 69 and parse_note("C3") == 48
    assert parse_note("F#3") == 54 and parse_note("Bb2") == 46
    assert abs(midi_to_freq(69) - 440) < 1e-9 and abs(freq_to_midi(261.6256) - 60) < 1e-3
    assert note_name(60) == "Do4" and note_name(69, True) == "A4"


def test_scales_and_chords():
    assert snap_to_scale(61.4, 48, SCALES["maior"]) == 62
    assert snap_to_scale(66.4, 48, SCALES["pentatonica"]) == 67
    assert chord_name([60, 64, 67]) == "Do maior"
    assert chord_name([62, 65, 69]) == "Re menor"
    assert chord_name([64, 67, 72]) == "Do maior/Mi"
    assert triad(62, "diatonico", 0, SCALES["maior"]) == [62, 65, 69]
    assert triad(67, "diatonico", 0, SCALES["maior"]) == [67, 71, 74]


def _peak(x):
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    return np.argmax(spec) * SAMPLE_RATE / len(x)


def test_oscillator_frequency():
    o = Oscillator(glide=0.0, amp_smoothing=0.0)
    o.target_freq, o.target_amp = 440, 1
    x = np.concatenate([o.render(256) for _ in range(200)])
    assert abs(_peak(x) - 440) < 2


def test_oscillator_has_no_clicks():
    for name in WAVES:
        o = Oscillator(wave=name)
        o.target_amp = 0.8
        chunks = []
        for i in range(400):
            o.target_freq = 130 + 400 * (i % 100) / 100
            chunks.append(o.render(256))
        y = np.concatenate(chunks)
        assert np.max(np.abs(np.diff(y))) < 0.25 and np.max(np.abs(y)) <= 1.0, name


def test_polysynth_chord_steal_and_decay():
    s = PolySynth(release=0.05)
    for k, m in enumerate((60, 64, 67)):
        s.note_on(k, midi_to_freq(m), 0.4)
    x = np.concatenate([s.render(256) for _ in range(150)])
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    fr = np.fft.rfftfreq(len(x), 1 / SAMPLE_RATE)
    for m in (60, 64, 67):
        f = midi_to_freq(m)
        assert spec[(fr > f * 0.98) & (fr < f * 1.02)].max() > spec.max() * 0.3
    assert np.max(np.abs(x)) < 1.0
    s.all_off()
    for _ in range(100):
        s.render(256)
    assert s.level < 1e-3
    for i in range(15):
        s.note_on(i, 200 + 10 * i, 0.3)
    assert sum(o is not None for o in s._owner) == 10
    d = PolySynth(decay=0.2)
    d.note_on("x", 440, 0.5)
    for _ in range(200):
        d.render(256)
    assert d._voices[d._owner.index("x")].target_amp < 0.05
    assert math.isfinite(d.level)
