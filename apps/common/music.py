"""Utilitarios musicais: notas <-> frequencias, escalas. Sem dependencias externas."""
import math

A4_FREQ = 440.0
A4_MIDI = 69

NOTE_NAMES = ("Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si")
NOTE_NAMES_EN = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

# intervalos (em semitons) a partir da tonica
SCALES = {
    "livre": None,                          # sem afinacao: glissando continuo
    "cromatica": (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11),
    "maior": (0, 2, 4, 5, 7, 9, 11),
    "menor": (0, 2, 3, 5, 7, 8, 10),
    "pentatonica": (0, 2, 4, 7, 9),
    "blues": (0, 3, 5, 6, 7, 10),
}


def midi_to_freq(midi: float) -> float:
    return A4_FREQ * 2 ** ((midi - A4_MIDI) / 12)


def freq_to_midi(freq: float) -> float:
    return A4_MIDI + 12 * math.log2(max(freq, 1e-6) / A4_FREQ)


def note_name(midi: int, english: bool = False) -> str:
    names = NOTE_NAMES_EN if english else NOTE_NAMES
    return f"{names[midi % 12]}{midi // 12 - 1}"


def parse_note(name: str) -> int:
    """'C3', 'A#4', 'Db2' -> numero MIDI."""
    name = name.strip().upper()
    base = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[name[0]]
    rest = name[1:]
    if rest.startswith("#"):
        base, rest = base + 1, rest[1:]
    elif rest.startswith("B"):
        base, rest = base - 1, rest[1:]
    return (int(rest) + 1) * 12 + base


def snap_to_scale(midi: float, root_midi: int, scale) -> float:
    """Arredonda para a nota mais proxima da escala (scale=None devolve igual)."""
    if scale is None:
        return midi
    best, best_d = midi, float("inf")
    octave = math.floor((midi - root_midi) / 12)
    for o in (octave - 1, octave, octave + 1):
        for step in scale:
            cand = root_midi + 12 * o + step
            d = abs(cand - midi)
            if d < best_d:
                best, best_d = cand, d
    return float(best)
