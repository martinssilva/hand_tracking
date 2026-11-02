"""
Circulo Cromatico Musical

Um circulo com as 12 notas, cada uma com uma cor. Toque nas fatias com os
dedos para tocar as notas. Cada anel e uma oitava (o de dentro e o mais grave).
Da para tocar com as duas maos ao mesmo tempo e em modo acorde.

Modos de tocar (--modo):
  pinca  (padrao) encoste o polegar no indicador em cima da fatia; a nota soa
         enquanto a pinca estiver fechada. Soltar = para. Mais preciso.
  toque  basta a ponta do indicador estar em cima da fatia.

Uso:
    python main.py circulo [--modo pinca] [--ordem cromatica] [--acorde nota]
                           [--escala livre] [--tonica C] [--oitava-base C3]
                           [--aneis 2] [--timbre teremim] [--decaimento 0]

Teclas: M modo | Q ordem (cromatica/quintas) | A acorde | E escala
        W timbre | H pontos da mao | ESC sai
"""
import argparse
import math

import cv2
import numpy as np

from apps.common import draw as ui
from apps.common.gestures import palm_size
from apps.common.music import (NOTE_NAMES, SCALES, chord_name, midi_to_freq,
                               note_name, parse_note, triad)
from apps.common.synth import WAVES, PolySynth

WINDOW = "Circulo Cromatico"
THUMB_TIP, INDEX_TIP = 4, 8
PINCH_ON, PINCH_OFF = 0.30, 0.45   # distancia polegar-indicador / tamanho da palma (histerese)

ORDERS = {
    "cromatica": tuple(range(12)),                      # Do Do# Re Re# ...
    "quintas": tuple((7 * i) % 12 for i in range(12)),  # Do Sol Re La Mi ...
}
CHORD_MODES = ("nota", "maior", "menor", "diatonico")
MODES = ("pinca", "toque")


# ---------- geometria (pura, sem OpenCV) ----------
class WheelLayout:
    """Circulo de 12 fatias x N aneis centrado na tela."""

    def __init__(self, width: int, height: int, rings: int):
        self.cx, self.cy = width / 2, height / 2
        self.r_out = 0.45 * height
        self.r_in = 0.15 * height
        self.rings = rings
        self.ring_w = (self.r_out - self.r_in) / rings

    def cell_at(self, x: float, y: float):
        """(posicao 0..11, anel) da fatia no pixel (x, y), ou None."""
        dx, dy = x - self.cx, y - self.cy
        r = math.hypot(dx, dy)
        if r < self.r_in or r >= self.r_out:
            return None
        # 0 graus = topo, sentido horario; cada fatia ocupa 30 graus centrada no seu angulo
        ang = (math.degrees(math.atan2(dx, -dy)) + 360 + 15) % 360
        return int(ang // 30) % 12, int((r - self.r_in) // self.ring_w)

    def _point(self, ang_deg: float, r: float):
        a = math.radians(ang_deg)
        return self.cx + r * math.sin(a), self.cy - r * math.cos(a)

    def polygon(self, pos: int, ring: int, steps: int = 10) -> np.ndarray:
        r1 = self.r_in + ring * self.ring_w
        r2 = r1 + self.ring_w
        a1, a2 = pos * 30 - 15, pos * 30 + 15
        angs = np.linspace(a1, a2, steps)
        outer = [self._point(a, r2) for a in angs]
        inner = [self._point(a, r1) for a in angs[::-1]]
        return np.array(outer + inner, np.int32)

    def label_pos(self, pos: int, ring: int):
        x, y = self._point(pos * 30, self.r_in + (ring + 0.5) * self.ring_w)
        return int(x), int(y)


def pitch_color(pos: int, sat: int, val: int):
    """Cor da fatia: o arco-iris completo da a volta no circulo."""
    hsv = np.uint8([[[pos * 15, sat, val]]])  # matiz do OpenCV vai de 0 a 180
    return tuple(int(c) for c in cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0, 0])


def hand_ids(hands):
    """Id estavel por mao: rotulo Left/Right do MediaPipe (desempata pelo indice)."""
    labels = [h.label for h in hands]
    return [lbl if labels.count(lbl) == 1 else f"{lbl}{i}" for i, lbl in enumerate(labels)]


# ---------- instrumento ----------
class ColorWheel:
    def __init__(self, synth: PolySynth, mode: str, order: str, chord_mode: str,
                 scale: str, tonic: int, base_midi: int, rings: int):
        self.synth = synth
        self.mode = mode
        self.order = order
        self.chord_mode = chord_mode
        self.scale = scale
        self.tonic = tonic % 12
        self.base = base_midi
        self.rings = rings
        self.layout = None
        self.pinching = {}      # id da mao -> pinca fechada?
        self.held = {}          # id da mao -> (celula, notas tocando)
        self.pointers = []      # (x, y, ativo, cor) para desenhar

    # --- notas ---
    def cell_midi(self, pos: int, ring: int) -> int:
        pc = ORDERS[self.order][pos]
        return self.base + 12 * ring + (pc - self.base % 12) % 12

    def notes_for(self, midi: int):
        if self.chord_mode == "nota":
            return [midi]
        return triad(midi, self.chord_mode, self.tonic, SCALES[self.scale])

    def in_scale(self, pc: int) -> bool:
        scale = SCALES[self.scale]
        return scale is None or (pc - self.tonic) % 12 in scale

    def playing_midis(self):
        return sorted({m for _, notes in self.held.values() for m in notes})

    # --- controles ---
    def _cycle(self, attr, options):
        options = list(options)
        setattr(self, attr, options[(options.index(getattr(self, attr)) + 1) % len(options)])
        self.release_all()

    def cycle_mode(self):  self._cycle("mode", MODES)
    def cycle_order(self): self._cycle("order", ORDERS)
    def cycle_chord(self): self._cycle("chord_mode", CHORD_MODES)
    def cycle_scale(self): self._cycle("scale", SCALES)

    def cycle_wave(self):
        names = list(WAVES)
        self.synth.wave = names[(names.index(self.synth.wave) + 1) % len(names)]

    def release_all(self):
        self.synth.all_off()
        self.held.clear()

    # --- logica por frame ---
    def _is_pinching(self, hid, pts) -> bool:
        d = math.dist(pts[THUMB_TIP], pts[INDEX_TIP]) / palm_size(pts)
        was = self.pinching.get(hid, False)
        now = d < (PINCH_OFF if was else PINCH_ON)
        self.pinching[hid] = now
        return now

    def update(self, hands, width: int, height: int):
        if self.layout is None or (self.layout.cx, self.layout.cy) != (width / 2, height / 2):
            self.layout = WheelLayout(width, height, self.rings)

        self.pointers = []
        seen = set()
        for hid, hand in zip(hand_ids(hands), hands):
            seen.add(hid)
            pts = hand.points
            if self.mode == "pinca":
                active = self._is_pinching(hid, pts)
                px = (pts[THUMB_TIP][0] + pts[INDEX_TIP][0]) / 2
                py = (pts[THUMB_TIP][1] + pts[INDEX_TIP][1]) / 2
            else:
                active = True
                px, py = pts[INDEX_TIP]
            x, y = px * width, py * height
            cell = self.layout.cell_at(x, y) if active else None
            self.pointers.append((int(x), int(y), cell is not None))
            self._set_hand_cell(hid, cell)

        for hid in list(self.held):   # maos que sumiram param de tocar
            if hid not in seen:
                self._set_hand_cell(hid, None)
        for hid in list(self.pinching):
            if hid not in seen:
                del self.pinching[hid]

    def _set_hand_cell(self, hid, cell):
        old_cell, old_notes = self.held.get(hid, (None, []))
        if cell == old_cell:
            return
        for m in old_notes:
            self.synth.note_off((hid, m))
        if cell is None:
            self.held.pop(hid, None)
            return
        notes = self.notes_for(self.cell_midi(*cell))
        velocity = 0.55 / math.sqrt(len(notes))
        for m in notes:
            self.synth.note_on((hid, m), midi_to_freq(m), velocity)
        self.held[hid] = (cell, notes)

    # --- desenho ---
    def draw(self, img):
        h, w = img.shape[:2]
        lay = self.layout or WheelLayout(w, h, self.rings)
        playing = set(self.playing_midis())
        touched = {cell for cell, _ in self.held.values()}

        overlay = img.copy()
        borders = []
        for ring in range(self.rings):
            for pos in range(12):
                pc = ORDERS[self.order][pos]
                midi = self.cell_midi(pos, ring)
                poly = lay.polygon(pos, ring)
                if midi in playing:
                    color = pitch_color(pos, 110, 255)
                elif self.in_scale(pc):
                    color = pitch_color(pos, 210, min(150 + 35 * ring, 235))  # agudo = mais claro
                else:
                    color = pitch_color(pos, 120, 70)
                cv2.fillPoly(overlay, [poly], color, cv2.LINE_AA)
                borders.append((poly, (pos, ring) in touched))
        cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)

        for poly, hot in sorted(borders, key=lambda b: b[1]):  # destacadas por ultimo
            cv2.polylines(img, [poly], True, ui.WHITE if hot else (40, 40, 40),
                          4 if hot else 1, cv2.LINE_AA)

        for ring in range(self.rings):
            for pos in range(12):
                midi = self.cell_midi(pos, ring)
                pc = midi % 12
                scale_ok = self.in_scale(pc)
                lx, ly = lay.label_pos(pos, ring)
                size = 0.5 + 0.08 * ring
                ui.text(img, note_name(midi), (lx, ly), size,
                        ui.WHITE if scale_ok else (150, 150, 150), 1, center=True)

        # centro: acorde / notas tocando
        cx, cy = int(lay.cx), int(lay.cy)
        cv2.circle(img, (cx, cy), int(lay.r_in) - 4, (25, 25, 25), -1, cv2.LINE_AA)
        if playing:
            name = chord_name(playing)
            if name:
                ui.text(img, name, (cx, cy - 12), 0.9 if len(name) < 10 else 0.7, ui.YELLOW, 2, center=True)
                ui.text(img, " ".join(NOTE_NAMES[m % 12] for m in sorted(playing)),
                        (cx, cy + 24), 0.5, ui.WHITE, 1, center=True)
            else:
                ui.text(img, " ".join(note_name(m) for m in sorted(playing)[:3]),
                        (cx, cy), 0.6, ui.YELLOW, 1, center=True)
        else:
            hint = "faca pinca" if self.mode == "pinca" else "toque"
            ui.text(img, hint, (cx, cy - 10), 0.6, (200, 200, 200), 1, center=True)
            ui.text(img, "numa nota", (cx, cy + 16), 0.6, (200, 200, 200), 1, center=True)

        for x, y, active in self.pointers:
            cv2.circle(img, (x, y), 12, ui.WHITE, -1 if active else 2, cv2.LINE_AA)
            cv2.circle(img, (x, y), 12, ui.BLACK, 1, cv2.LINE_AA)

        # informacoes
        info = [f"modo: {self.mode}", f"ordem: {self.order}", f"acorde: {self.chord_mode}",
                f"escala: {'todas' if SCALES[self.scale] is None else NOTE_NAMES[self.tonic] + ' ' + self.scale}",
                f"timbre: {self.synth.wave}"]
        ui.panel(img, 0, 0, 250, 30 + 26 * len(info), alpha=0.55)
        for i, line in enumerate(info):
            ui.text(img, line, (12, 28 + 26 * i), 0.55, ui.WHITE, 1)
        ui.panel(img, 0, h - 34, w, h, alpha=0.6)
        ui.text(img, "M modo | Q ordem | A acorde | E escala | W timbre | H pontos | ESC sai",
                (12, h - 11), 0.5, ui.WHITE, 1)


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="circulo", description="Circulo cromatico musical")
    p.add_argument("--modo", default="pinca", choices=MODES,
                   help="pinca: polegar no indicador toca; toque: so encostar o dedo")
    p.add_argument("--ordem", default="cromatica", choices=list(ORDERS),
                   help="cromatica (Do Do# Re...) ou quintas (Do Sol Re La...)")
    p.add_argument("--acorde", default="nota", choices=CHORD_MODES,
                   help="nota = uma nota; maior/menor/diatonico = toca um acorde")
    p.add_argument("--escala", default="livre", choices=list(SCALES),
                   help="destaca as notas da escala (livre = todas)")
    p.add_argument("--tonica", default="C", help="tonica da escala (padrao C)")
    p.add_argument("--oitava-base", default="C3", help="nota do anel de dentro (padrao C3)")
    p.add_argument("--aneis", type=int, default=2, help="numero de oitavas/aneis (1 a 4)")
    p.add_argument("--timbre", default="teremim", choices=list(WAVES))
    p.add_argument("--decaimento", type=float, default=0.0,
                   help="segundos para a nota sumir mesmo segurada (0 = sustenta)")
    p.add_argument("--camera", type=int, default=0)
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        base = parse_note(args.oitava_base)
        tonic = parse_note(args.tonica if args.tonica[-1].isdigit() else args.tonica + "4")
    except (KeyError, ValueError, IndexError):
        raise SystemExit("Nota invalida (exemplos: --tonica G, --oitava-base C3)")

    from apps.common.synth import AudioOutput
    from apps.common.tracker import HandTracker, open_camera

    synth = PolySynth(wave=args.timbre, decay=max(0.0, args.decaimento))
    wheel = ColorWheel(synth, args.modo, args.ordem, args.acorde, args.escala, tonic,
                       base, min(max(args.aneis, 1), 4))
    cap = open_camera(args.camera)
    tracker = HandTracker(max_hands=2)
    show_landmarks = False

    keys = {ord("m"): wheel.cycle_mode, ord("q"): wheel.cycle_order,
            ord("a"): wheel.cycle_chord, ord("e"): wheel.cycle_scale,
            ord("w"): wheel.cycle_wave}

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    try:
        with AudioOutput(synth):
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                frame = cv2.flip(frame, 1)
                h, w = frame.shape[:2]
                hands = tracker.process(frame)
                wheel.update(hands, w, h)
                wheel.draw(frame)
                if show_landmarks:
                    for hand in hands:
                        tracker.draw(frame, hand)
                cv2.imshow(WINDOW, frame)

                key = cv2.waitKey(1) & 0xFF
                if key == 27:
                    break
                if key in (ord("h"), ord("H")):
                    show_landmarks = not show_landmarks
                elif key < 128 and ord(chr(key).lower()) in keys:
                    keys[ord(chr(key).lower())]()
                if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                    break
            synth.all_off()
    finally:
        cap.release()
        tracker.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
