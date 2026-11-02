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


# intervalos do acorde (a partir da fundamental) -> sufixo mostrado
CHORDS = (
    ((0, 4, 7), " maior"), ((0, 3, 7), " menor"), ((0, 3, 6), " dim"), ((0, 4, 8), " aum"),
    ((0, 4, 7, 10), "7"), ((0, 4, 7, 11), "7M"), ((0, 3, 7, 10), "m7"), ((0, 3, 6, 10), "m7(b5)"),
    ((0, 5, 7), "sus4"), ((0, 2, 7), "sus2"), ((0, 7), "5"),
)


def chord_name(midis) -> str:
    """Nome do acorde formado pelas notas (ex.: 'Do maior'), ou '' se nao reconhecer."""
    pcs = {m % 12 for m in midis}
    if len(pcs) < 2:
        return ""
    lowest = min(midis) % 12
    # tenta primeiro com a nota mais grave como fundamental
    for root in sorted(pcs, key=lambda p: p != lowest):
        intervals = tuple(sorted((p - root) % 12 for p in pcs))
        for pattern, suffix in CHORDS:
            if intervals == pattern:
                name = NOTE_NAMES[root] + suffix
                return name if root == lowest else f"{name}/{NOTE_NAMES[lowest]}"
    return ""


def triad(root_midi: int, quality: str, tonic: int = 0, scale=None):
    """
    Notas de um acorde de 3 sons. quality: 'maior', 'menor' ou 'diatonico'
    (usa as notas da escala: em Do maior, Re vira Re menor, Sol vira Sol maior...).
    """
    if quality == "menor":
        return [root_midi, root_midi + 3, root_midi + 7]
    if quality == "diatonico" and scale and len(scale) >= 5:
        degree = (root_midi - tonic) % 12
        if degree in scale:
            i = scale.index(degree)
            notes = []
            for k in (0, 2, 4):
                j = i + k
                step = scale[j % len(scale)] + 12 * (j // len(scale))
                notes.append(root_midi + step - degree)
            return notes
    return [root_midi, root_midi + 4, root_midi + 7]
