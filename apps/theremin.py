"""
Simulador de Teremim

Como no instrumento de verdade, cada mao controla uma coisa:
  - Mao da DIREITA (lado direito da tela): ALTURA da nota.
    Ponta do indicador mais alta = nota mais aguda.
    Fechar a mao (punho) silencia: da para "articular" as notas.
  - Mao da ESQUERDA (lado esquerdo da tela): VOLUME.
    Mao mais alta = mais alto. Sem a mao esquerda, usa o volume fixo (--volume).

Uso:
    python main.py teremim [--nota-base C3] [--oitavas 2] [--escala livre]
                           [--timbre teremim] [--volume 0.7] [--camera 0]

Teclas: Q troca a escala | W troca o timbre | V liga/desliga vibrato
        H mostra/esconde os pontos da mao | ESC sai
"""
import argparse

import cv2
import numpy as np

from apps.common import draw as ui
from apps.common.gestures import GESTURES_BY_KEY, fingers_extended
from apps.common.music import (SCALES, freq_to_midi, midi_to_freq, note_name,
                               parse_note, snap_to_scale)
from apps.common.synth import WAVES, Oscillator

WINDOW = "Teremim"
TOP, BOTTOM = 0.10, 0.92      # faixa util da tela (normalizada) para a altura
VOL_TOP, VOL_BOTTOM = 0.15, 0.85
INDEX_TIP, MIDDLE_MCP = 8, 9
VIBRATO_DEPTH = 0.25          # semitons
SNAP_HYSTERESIS = 0.2         # semitons: evita a nota ficar pulando na fronteira

CYAN = (230, 200, 60)
GRID = (200, 200, 200)


# ---------- mapeamentos (funcoes puras, faceis de testar) ----------
def y_to_midi(y: float, low_midi: int, octaves: int) -> float:
    frac = (BOTTOM - y) / (BOTTOM - TOP)
    frac = min(max(frac, 0.0), 1.0)
    return low_midi + frac * octaves * 12


def midi_to_y(midi: float, low_midi: int, octaves: int) -> float:
    frac = (midi - low_midi) / (octaves * 12)
    return BOTTOM - frac * (BOTTOM - TOP)


def y_to_volume(y: float) -> float:
    frac = (VOL_BOTTOM - y) / (VOL_BOTTOM - VOL_TOP)
    return min(max(frac, 0.0), 1.0)


def assign_hands(hands):
    """Retorna (mao_altura, mao_volume). A mais a direita controla a altura."""
    if not hands:
        return None, None
    if len(hands) == 1:
        h = hands[0]
        return (h, None) if h.points[MIDDLE_MCP][0] >= 0.5 else (None, h)
    ordered = sorted(hands, key=lambda h: h.points[MIDDLE_MCP][0])
    return ordered[-1], ordered[0]


class Theremin:
    def __init__(self, osc: Oscillator, low_midi: int, octaves: int, scale: str,
                 default_volume: float):
        self.osc = osc
        self.low = low_midi
        self.octaves = octaves
        self.scale_names = list(SCALES)
        self.scale = scale
        self.default_volume = default_volume
        self.current_midi = None   # nota atual (apos afinacao)
        self.raw_midi = None
        self.volume = 0.0
        self.muted = False
        self.pitch_pt = None
        self.volume_pt = None

    # --- controles ---
    def cycle_scale(self):
        i = self.scale_names.index(self.scale)
        self.scale = self.scale_names[(i + 1) % len(self.scale_names)]
        self.current_midi = None

    def cycle_wave(self):
        names = list(WAVES)
        self.osc.wave = names[(names.index(self.osc.wave) + 1) % len(names)]

    def toggle_vibrato(self):
        self.osc.vibrato_depth = 0.0 if self.osc.vibrato_depth else VIBRATO_DEPTH

    # --- logica por frame ---
    def update(self, pitch_hand, volume_hand):
        self.pitch_pt = pitch_hand.points[INDEX_TIP] if pitch_hand else None
        self.volume_pt = volume_hand.points[MIDDLE_MCP] if volume_hand else None

        self.volume = y_to_volume(self.volume_pt[1]) if volume_hand else self.default_volume

        if pitch_hand is None:
            self.muted = True
            self.osc.target_amp = 0.0
            return

        self.muted = GESTURES_BY_KEY["punho"].matches(pitch_hand.points,
                                                      fingers_extended(pitch_hand.points))
        raw = y_to_midi(self.pitch_pt[1], self.low, self.octaves)
        self.raw_midi = raw
        scale = SCALES[self.scale]
        if scale is None:
            self.current_midi = raw
        else:
            cand = snap_to_scale(raw, self.low, scale)
            cur = self.current_midi
            if cur is None or abs(raw - cand) + SNAP_HYSTERESIS < abs(raw - cur):
                self.current_midi = cand

        self.osc.target_freq = midi_to_freq(self.current_midi)
        self.osc.target_amp = 0.0 if self.muted else self.volume * 0.8

    # --- desenho ---
    def draw(self, img, show_help=True):
        h, w = img.shape[:2]
        mid = w // 2
        scale = SCALES[self.scale]

        # zona da altura (direita): linhas das notas
        ui.panel(img, mid, 0, w, h, (30, 20, 10), 0.35)
        for m in range(self.low, self.low + self.octaves * 12 + 1):
            step = (m - self.low) % 12
            in_scale = scale is None or step in scale
            natural = "#" not in note_name(m)
            if not in_scale or (scale is None and not natural):
                continue
            y = int(midi_to_y(m, self.low, self.octaves) * h)
            is_root = step == 0
            color = ui.YELLOW if is_root else GRID
            cv2.line(img, (mid + 70, y), (w - 10, y), color, 2 if is_root else 1, cv2.LINE_AA)
            ui.text(img, note_name(m), (mid + 8, y + 7), 0.55, color, 1)

        # zona do volume (esquerda): barra vertical
        bx, by1, by2 = 30, int(VOL_TOP * h), int(VOL_BOTTOM * h)
        cv2.rectangle(img, (bx, by1), (bx + 30, by2), (60, 60, 60), -1)
        fill_y = int(by2 - (by2 - by1) * self.volume)
        cv2.rectangle(img, (bx, fill_y), (bx + 30, by2), ui.GREEN, -1)
        cv2.rectangle(img, (bx, by1), (bx + 30, by2), ui.WHITE, 1)
        ui.text(img, "VOLUME", (bx - 5, by1 - 15), 0.6)
        ui.text(img, f"{int(self.volume * 100)}%", (bx - 5, by2 + 28), 0.6)
        if self.volume_pt is None:
            ui.text(img, "(fixo)", (bx - 5, by2 + 52), 0.5, (180, 180, 180), 1)
        else:
            vy = int(self.volume_pt[1] * h)
            cv2.line(img, (bx + 30, vy), (int(self.volume_pt[0] * w), vy), ui.GREEN, 1, cv2.LINE_AA)
        cv2.line(img, (mid, 0), (mid, h), (120, 120, 120), 1)

        # marcador da altura
        if self.pitch_pt is not None and self.current_midi is not None:
            px, py = int(self.pitch_pt[0] * w), int(self.pitch_pt[1] * h)
            ny = int(midi_to_y(self.current_midi, self.low, self.octaves) * h)
            color = (120, 120, 120) if self.muted else CYAN
            cv2.line(img, (mid + 70, ny), (w, ny), color, 3, cv2.LINE_AA)
            cv2.circle(img, (px, py), 14, color, 3, cv2.LINE_AA)
            if abs(ny - py) > 3:
                cv2.line(img, (px, py), (px, ny), color, 1, cv2.LINE_AA)

        self._draw_readout(img)
        self._draw_scope(img)
        if show_help:
            ui.panel(img, 0, h - 34, w, h, alpha=0.6)
            ui.text(img, "Q escala | W timbre | V vibrato | H pontos | Punho na direita = silencio | ESC sai",
                    (12, h - 11), 0.5, ui.WHITE, 1)

    def _draw_readout(self, img):
        h, w = img.shape[:2]
        x = 110
        ui.panel(img, x - 10, 10, x + 360, 160, alpha=0.6)
        if self.current_midi is None or self.pitch_pt is None:
            ui.text(img, "Coloque a mao direita", (x, 55), 0.8, ui.YELLOW)
            ui.text(img, "no lado direito da tela", (x, 90), 0.8, ui.YELLOW)
        else:
            freq = midi_to_freq(self.current_midi)
            nearest = int(round(self.current_midi))
            cents = int(round((self.current_midi - nearest) * 100))
            color = (150, 150, 150) if self.muted else ui.WHITE
            ui.text(img, note_name(nearest), (x, 70), 1.8, color, 3)
            ui.text(img, f"{freq:7.1f} Hz", (x + 175, 50), 0.7, color, 1)
            ui.text(img, f"{cents:+d} cents", (x + 175, 80), 0.7, color, 1)
            # afinador: barra de -50 a +50 cents
            cx, cy = x + 170, 115
            cv2.line(img, (cx - 150, cy), (cx + 150, cy), (120, 120, 120), 2)
            cv2.line(img, (cx, cy - 10), (cx, cy + 10), ui.WHITE, 2)
            mx = cx + int(cents * 3)
            tune_color = ui.GREEN if abs(cents) < 10 else ui.YELLOW if abs(cents) < 25 else ui.RED
            cv2.circle(img, (mx, cy), 8, tune_color, -1, cv2.LINE_AA)
            if self.muted:
                ui.text(img, "MUDO", (x + 260, 145), 0.6, ui.RED, 1)
        ui.text(img, f"escala: {self.scale}  timbre: {self.osc.wave}"
                     f"{'  vibrato' if self.osc.vibrato_depth else ''}",
                (x, 150), 0.5, (200, 200, 200), 1)

    def _draw_scope(self, img):
        """Mini osciloscopio com a forma de onda atual."""
        h, w = img.shape[:2]
        x1, y1, x2, y2 = 100, 170, 470, 250
        ui.panel(img, x1, y1, x2, y2, alpha=0.6)
        amp = min(self.osc.amp / 0.8, 1.0)
        if amp < 0.01:
            cv2.line(img, (x1 + 5, (y1 + y2) // 2), (x2 - 5, (y1 + y2) // 2), CYAN, 1)
            return
        cycles = 1.5 + 4 * (freq_to_midi(self.osc.freq) - self.low) / (self.octaves * 12)
        phase = np.linspace(0, cycles, x2 - x1 - 10)
        wave = WAVES[self.osc.wave](phase) * amp
        ys = ((y1 + y2) / 2 - wave * (y2 - y1) / 2.3).astype(np.int32)
        xs = np.arange(x1 + 5, x2 - 5, dtype=np.int32)[: len(ys)]
        cv2.polylines(img, [np.stack([xs, ys], axis=1)], False, CYAN, 2, cv2.LINE_AA)


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="teremim", description="Simulador de teremim com as maos")
    p.add_argument("--nota-base", default="C3", help="nota mais grave (padrao C3)")
    p.add_argument("--oitavas", type=int, default=2, help="extensao em oitavas (padrao 2)")
    p.add_argument("--escala", default="livre", choices=list(SCALES),
                   help="livre = glissando continuo; as outras afinam nas notas")
    p.add_argument("--timbre", default="teremim", choices=list(WAVES))
    p.add_argument("--volume", type=float, default=0.7,
                   help="volume quando nao ha mao esquerda (0 a 1, padrao 0.7)")
    p.add_argument("--glide", type=float, default=0.06,
                   help="suavidade da troca de nota em segundos (padrao 0.06)")
    p.add_argument("--vibrato", action="store_true", help="comeca com vibrato ligado")
    p.add_argument("--camera", type=int, default=0)
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        low = parse_note(args.nota_base)
    except (KeyError, ValueError, IndexError):
        raise SystemExit(f"Nota invalida: {args.nota_base} (exemplos: C3, A2, F#3)")

    from apps.common.synth import AudioOutput
    from apps.common.tracker import HandTracker, open_camera

    osc = Oscillator(glide=args.glide, wave=args.timbre,
                     vibrato_depth=VIBRATO_DEPTH if args.vibrato else 0.0)
    theremin = Theremin(osc, low, max(1, args.oitavas), args.escala,
                        min(max(args.volume, 0.0), 1.0))
    cap = open_camera(args.camera)
    tracker = HandTracker(max_hands=2)
    show_landmarks = False

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    try:
        with AudioOutput(osc):
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                frame = cv2.flip(frame, 1)
                hands = tracker.process(frame)
                pitch_hand, volume_hand = assign_hands(hands)
                theremin.update(pitch_hand, volume_hand)

                if show_landmarks:
                    for hand in hands:
                        tracker.draw(frame, hand)
                theremin.draw(frame)
                cv2.imshow(WINDOW, frame)

                key = cv2.waitKey(1) & 0xFF
                if key == 27:
                    break
                elif key in (ord("q"), ord("Q")):
                    theremin.cycle_scale()
                elif key in (ord("w"), ord("W")):
                    theremin.cycle_wave()
                elif key in (ord("v"), ord("V")):
                    theremin.toggle_vibrato()
                elif key in (ord("h"), ord("H")):
                    show_landmarks = not show_landmarks
                if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                    break
    finally:
        cap.release()
        tracker.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
