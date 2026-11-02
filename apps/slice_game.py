"""
Jogo "Corte no Ar"

Frutas sao lancadas de baixo da tela e voce corta com o dedo indicador, num
movimento rapido (mao parada nao corta). Cortar varias frutas no mesmo golpe
da bonus de combo. Fruta que cai sem ser cortada tira uma vida; bomba cortada
tambem. Com as vidas zeradas o jogo acaba.

Modo 2 jogadores (--jogadores 2): a tela e dividida ao meio, cada jogador
corta so as frutas do seu lado e tem placar e vidas separados.

Uso:
    python main.py corte [--jogadores 1] [--vidas 3] [--velocidade 1.0]
                         [--bomba-fatal] [--sem-som] [--camera 0]

Teclas: ESPACO comeca/reinicia | H mostra os pontos da mao | ESC sai
"""
import argparse
import math
import random
from collections import deque
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2

from apps.common import draw as ui
from apps.common.game import (HoldTimer, Scoreboard, draw_game_over, draw_hud,
                              draw_start_screen, run_game)
from apps.common.gestures import classify

WINDOW = "Corte no Ar"
INDEX_TIP, WRIST, MIDDLE_MCP = 8, 0, 9

GRAVITY = 1.5            # em alturas de tela por segundo^2
CUT_SPEED = 3.5          # velocidade minima do dedo para cortar, em palmas por segundo
TRAIL_TIME = 0.15        # segundos de rastro da lamina
COMBO_WINDOW = 0.3       # segundos entre cortes para contar como o mesmo golpe
COMBO_MIN = 3            # frutas no mesmo golpe para ganhar bonus
START_HOLD_TIME = 1.0    # segundos de mao aberta para comecar
RESTART_DELAY = 1.5      # segundos no fim de jogo antes de aceitar reinicio
FRUIT_RADIUS = 0.055     # raio base, em alturas de tela

START, PLAYING, GAME_OVER = range(3)

Color = Tuple[int, int, int]


@dataclass(frozen=True)
class FruitKind:
    name: str
    skin: Color
    flesh: Color
    size: float      # multiplica FRUIT_RADIUS
    points: int
    stripes: bool = False


FRUITS = (
    FruitKind("maca",     (40, 40, 210),  (190, 230, 245), 1.00, 1),
    FruitKind("laranja",  (0, 140, 255),  (80, 190, 255),  1.00, 1),
    FruitKind("limao",    (40, 220, 235), (160, 245, 250), 0.85, 1),
    FruitKind("ameixa",   (120, 40, 110), (110, 200, 240), 0.80, 2),   # menor = vale mais
    FruitKind("melancia", (40, 140, 40),  (80, 60, 230),   1.35, 1, stripes=True),
)
BOMB = FruitKind("bomba", (45, 45, 45), (0, 120, 255), 0.90, 0)


# ---------- geometria (funcoes puras) ----------
def point_segment_distance(p, a, b) -> float:
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def segment_hits_circle(a, b, center, radius) -> bool:
    """O segmento a-b (movimento do dedo num frame) encosta no circulo?"""
    return point_segment_distance(center, a, b) <= radius


def launch_velocity(x0: float, x_target: float, apex_height: float, gravity: float):
    """
    Velocidade inicial (vx, vy) para um lancamento que sobe `apex_height`
    pixels e cai de volta na altura de partida em x_target.
    """
    vy = -math.sqrt(2 * gravity * apex_height)   # negativo = para cima
    flight = 2 * -vy / gravity
    return (x_target - x0) / flight, vy


def hand_keys(hands) -> List[str]:
    """Id estavel por mao (rotulo do MediaPipe, desempatado pelo indice)."""
    labels = [getattr(h, "label", "?") for h in hands]
    return [lbl if labels.count(lbl) == 1 else f"{lbl}{i}" for i, lbl in enumerate(labels)]


# ---------- objetos do jogo ----------
@dataclass
class Fruit:
    kind: FruitKind
    x: float
    y: float
    vx: float
    vy: float
    r: float
    owner: int = 0
    angle: float = 0.0
    spin: float = 0.0

    @property
    def is_bomb(self) -> bool:
        return self.kind is BOMB

    def step(self, dt: float, gravity: float):
        self.vy += gravity * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.angle += self.spin * dt


@dataclass
class Piece:
    """Metade de fruta, particula ou texto flutuante (tudo que cai e some)."""
    x: float
    y: float
    vx: float
    vy: float
    life: float                 # segundos restantes
    kind: str                   # "half", "drop", "text", "miss"
    color: Color = (255, 255, 255)
    r: float = 4.0
    angle: float = 0.0
    spin: float = 0.0
    fruit: Optional[FruitKind] = None
    text: str = ""
    gravity: bool = True


class Blade:
    """Rastro do indicador de uma mao. Corta quando o dedo esta rapido."""

    def __init__(self):
        self.trail = deque()    # (x, y, t)
        self.speed = 0.0        # palmas por segundo

    def add(self, x: float, y: float, t: float, palm_px: float):
        if self.trail:
            px, py, pt = self.trail[-1]
            dt = t - pt
            if dt > 0:
                self.speed = math.hypot(x - px, y - py) / dt / max(palm_px, 1.0)
        self.trail.append((x, y, t))
        while self.trail and t - self.trail[0][2] > TRAIL_TIME:
            self.trail.popleft()

    @property
    def cutting(self) -> bool:
        return len(self.trail) >= 2 and self.speed >= CUT_SPEED

    def last_segment(self):
        (x1, y1, _), (x2, y2, _) = self.trail[-2], self.trail[-1]
        return (x1, y1), (x2, y2)


class Player:
    def __init__(self, index: int, lives: int):
        self.index = index
        self.board = Scoreboard(lives)
        self.x1 = self.x2 = 0
        self.reset(0.0)

    def reset(self, now: float):
        self.board.reset()
        self.sliced = 0
        self.best_combo = 0
        self.combo = 0
        self.combo_last = 0.0
        self.combo_pos = (0.0, 0.0)
        self.started_at = now
        self.next_wave = now + 1.0
        self.pending = []           # (tempo, Fruit) aguardando lancamento


class SoundFx:
    """Efeitos sonoros curtos com o PolySynth. Sem placa de som, fica mudo."""

    def __init__(self, enabled: bool):
        self.synth = None
        self._out = None
        self._release = []
        if not enabled:
            return
        try:
            from apps.common.synth import AudioOutput, PolySynth
            self.synth = PolySynth(voices=8, wave="triangulo", attack=0.003,
                                   release=0.12, master=0.8)
            self._out = AudioOutput(self.synth)
            self._out.__enter__()
        except SystemExit as e:  # AudioOutput avisa com SystemExit quando nao ha audio
            print(f"{e}\nSeguindo sem som.")
            self.synth = self._out = None

    def blip(self, midi: float, velocity: float = 0.35):
        if self.synth is None:
            return
        key = object()
        self.synth.note_on(key, 440.0 * 2 ** ((midi - 69) / 12), velocity)
        self._release.append(key)

    def tick(self):
        """Chamar uma vez por frame: solta as notas do frame anterior (som curto)."""
        if self.synth is None:
            return
        release, self._release = self._release, []
        for key in release:
            self.synth.note_off(key)

    def close(self):
        if self._out is not None:
            self._out.__exit__(None, None, None)


# ---------- jogo ----------
class SliceGame:
    def __init__(self, players: int = 1, lives: int = 3, speed: float = 1.0,
                 bomb_fatal: bool = False, sound: Optional[SoundFx] = None,
                 seed: Optional[int] = None):
        self.players = [Player(i, lives) for i in range(max(1, min(players, 2)))]
        self.speed = speed
        self.bomb_fatal = bomb_fatal
        self.sound = sound or SoundFx(False)
        self.rng = random.Random(seed)
        self.state = START
        self.debug_landmarks = False
        self.start_hold = HoldTimer()
        self.w, self.h = 1280, 720
        self.fruits: List[Fruit] = []
        self.pieces: List[Piece] = []
        self.blades = {}            # id da mao -> Blade
        self.blade_owner = {}       # id da mao -> indice do jogador
        self.flash = 0.0
        self.last_time = None
        self.ended_at = 0.0
        self._layout()

    # --- configuracao ---
    def _layout(self):
        n = len(self.players)
        for p in self.players:
            p.x1 = int(self.w * p.index / n)
            p.x2 = int(self.w * (p.index + 1) / n)

    @property
    def gravity(self) -> float:
        return GRAVITY * self.h

    @property
    def show_landmarks(self) -> bool:
        return self.debug_landmarks

    def start(self, now: float):
        self.state = PLAYING
        self.fruits.clear()
        self.pieces.clear()
        self.flash = 0.0
        for p in self.players:
            p.reset(now)

    def on_key(self, key: int, now: float):
        if key == ord(" ") and (self.state == START or self._can_restart(now)):
            self.start(now)
        elif key in (ord("h"), ord("H")):
            self.debug_landmarks = not self.debug_landmarks

    def _can_restart(self, now: float) -> bool:
        return self.state == GAME_OVER and now - self.ended_at >= RESTART_DELAY

    # --- dificuldade e lancamentos ---
    def _difficulty(self, elapsed: float):
        interval = max(1.0, 2.4 - 0.02 * elapsed)
        max_wave = min(6, 1 + int(elapsed / 15))
        bomb_chance = 0.0 if elapsed < 8 else min(0.35, 0.08 + 0.004 * elapsed)
        return interval, max_wave, bomb_chance

    def _make_fruit(self, player: Player, kind: FruitKind) -> Fruit:
        span = player.x2 - player.x1
        margin = 0.12 * span
        r = FRUIT_RADIUS * self.h * kind.size
        x0 = self.rng.uniform(player.x1 + margin, player.x2 - margin)
        x_target = self.rng.uniform(player.x1 + margin, player.x2 - margin)
        apex = self.rng.uniform(0.55, 0.85) * self.h
        vx, vy = launch_velocity(x0, x_target, apex, self.gravity)
        return Fruit(kind, x0, self.h + r, vx, vy, r, owner=player.index,
                     spin=self.rng.uniform(-3, 3))

    def _schedule_waves(self, now: float):
        for p in self.players:
            if not p.board.alive or now < p.next_wave:
                continue
            interval, max_wave, bomb_chance = self._difficulty(now - p.started_at)
            count = self.rng.randint(1, max_wave)
            bomb_slot = self.rng.randrange(count) if self.rng.random() < bomb_chance else -1
            for i in range(count):
                kind = BOMB if i == bomb_slot else self.rng.choice(FRUITS)
                p.pending.append((now + 0.18 * i, self._make_fruit(p, kind)))
            p.next_wave = now + interval

    def _launch_pending(self, now: float):
        for p in self.players:
            ready = [f for t, f in p.pending if t <= now]
            p.pending = [(t, f) for t, f in p.pending if t > now]
            if p.board.alive:
                self.fruits.extend(ready)

    # --- cortes ---
    def _update_blades(self, now: float, hands):
        seen = set()
        for key, hand in zip(hand_keys(hands), hands):
            seen.add(key)
            pts = hand.points
            x, y = pts[INDEX_TIP][0] * self.w, pts[INDEX_TIP][1] * self.h
            palm_px = math.hypot((pts[WRIST][0] - pts[MIDDLE_MCP][0]) * self.w,
                                 (pts[WRIST][1] - pts[MIDDLE_MCP][1]) * self.h)
            self.blades.setdefault(key, Blade()).add(x, y, now, palm_px)
            self.blade_owner[key] = 0 if len(self.players) == 1 else int(x >= self.w / 2)
        for key in list(self.blades):   # mao sumiu: lamina some
            if key not in seen:
                del self.blades[key]
                self.blade_owner.pop(key, None)

    def _cut(self, now: float):
        for key, blade in self.blades.items():
            if not blade.cutting:
                continue
            player = self.players[self.blade_owner[key]]
            if not player.board.alive:
                continue
            a, b = blade.last_segment()
            for fruit in list(self.fruits):
                if fruit.owner == player.index and segment_hits_circle(a, b, (fruit.x, fruit.y), fruit.r):
                    self.fruits.remove(fruit)
                    direction = math.atan2(b[1] - a[1], b[0] - a[0])
                    if fruit.is_bomb:
                        self._explode(now, player, fruit)
                    else:
                        self._slice(now, player, fruit, direction)

    def _slice(self, now: float, player: Player, fruit: Fruit, direction: float):
        player.board.add(fruit.kind.points)
        player.sliced += 1
        if now - player.combo_last > COMBO_WINDOW:
            player.combo = 0
        player.combo += 1
        player.combo_last = now
        player.combo_pos = (fruit.x, fruit.y)
        self.sound.blip(76 + 2 * min(player.combo, 8))

        # duas metades se afastando na perpendicular do corte
        nx, ny = -math.sin(direction), math.cos(direction)
        push = 0.25 * self.h
        for side in (1, -1):
            self.pieces.append(Piece(
                fruit.x + side * nx * fruit.r * 0.3, fruit.y + side * ny * fruit.r * 0.3,
                fruit.vx * 0.5 + side * nx * push, min(fruit.vy, 0) * 0.3 + side * ny * push,
                life=1.5, kind="half", r=fruit.r, fruit=fruit.kind,
                angle=math.degrees(direction) + (0 if side == 1 else 180),
                spin=side * self.rng.uniform(60, 160)))
        for _ in range(10):  # respingos
            ang = self.rng.uniform(0, 2 * math.pi)
            spd = self.rng.uniform(0.1, 0.5) * self.h
            self.pieces.append(Piece(fruit.x, fruit.y, math.cos(ang) * spd, math.sin(ang) * spd,
                                     life=self.rng.uniform(0.3, 0.7), kind="drop",
                                     color=fruit.kind.flesh, r=self.rng.uniform(3, 7)))
        self._popup(fruit.x, fruit.y - fruit.r, f"+{fruit.kind.points}", ui.WHITE)

    def _explode(self, now: float, player: Player, bomb: Fruit):
        if self.bomb_fatal:
            player.board.lives = 0
        else:
            player.board.lose_life()
        self.flash = 0.35
        self.sound.blip(36, 0.6)
        for _ in range(24):
            ang = self.rng.uniform(0, 2 * math.pi)
            spd = self.rng.uniform(0.2, 0.8) * self.h
            color = self.rng.choice([(0, 120, 255), (0, 200, 255), (60, 60, 60)])
            self.pieces.append(Piece(bomb.x, bomb.y, math.cos(ang) * spd, math.sin(ang) * spd,
                                     life=self.rng.uniform(0.3, 0.8), kind="drop",
                                     color=color, r=self.rng.uniform(4, 10), gravity=False))
        self._popup(bomb.x, bomb.y - bomb.r, "BOMBA!", ui.RED)

    def _popup(self, x, y, text, color):
        self.pieces.append(Piece(x, y, 0, -0.12 * self.h, life=0.8, kind="text",
                                 color=color, text=text, gravity=False))

    def _resolve_combos(self, now: float):
        for p in self.players:
            if p.combo and now - p.combo_last > COMBO_WINDOW:
                if p.combo >= COMBO_MIN:
                    p.board.add(p.combo)
                    x, y = p.combo_pos
                    self._popup(x, y - 40, f"COMBO x{p.combo}  +{p.combo}", ui.YELLOW)
                    self.sound.blip(88, 0.4)
                p.best_combo = max(p.best_combo, p.combo)
                p.combo = 0

    # --- fisica ---
    def _step_physics(self, dt: float):
        g = self.gravity
        for f in list(self.fruits):
            f.step(dt, g)
            if f.vy > 0 and f.y - f.r > self.h:   # caiu sem ser cortada
                self.fruits.remove(f)
                player = self.players[f.owner]
                if not f.is_bomb and self.state == PLAYING and player.board.alive:
                    player.board.lose_life()
                    self.sound.blip(45, 0.3)
                    self.pieces.append(Piece(min(max(f.x, 30), self.w - 30), self.h - 40, 0, 0,
                                             life=1.0, kind="miss", gravity=False))
        for pc in list(self.pieces):
            if pc.gravity:
                pc.vy += g * dt
            pc.x += pc.vx * dt
            pc.y += pc.vy * dt
            pc.angle += pc.spin * dt
            pc.life -= dt
            if pc.life <= 0 or pc.y - pc.r > self.h + 50:
                self.pieces.remove(pc)
        self.flash = max(0.0, self.flash - dt)

    # --- interface do run_game ---
    def process(self, now: float, hands, width: int, height: int):
        if (width, height) != (self.w, self.h):
            self.w, self.h = width, height
            self._layout()
        dt = 0.0 if self.last_time is None else min(now - self.last_time, 0.05)
        self.last_time = now
        self.sound.tick()
        self._update_blades(now, hands)

        if self.state in (START, GAME_OVER):
            open_hand = any(g is not None and g.key == "aberta"
                            for g in (classify(h.points) for h in hands))
            can_start = self.state == START or self._can_restart(now)
            if self.start_hold.update(now, open_hand and can_start) > START_HOLD_TIME:
                self.start_hold.reset()
                self.start(now)
                return

        if self.state == PLAYING:
            self._schedule_waves(now)
            self._launch_pending(now)
            self._cut(now)
            self._resolve_combos(now)

        self._step_physics(dt * self.speed)

        if self.state == PLAYING and not any(p.board.alive for p in self.players):
            self._resolve_combos(now + COMBO_WINDOW + 1)
            for p in self.players:
                p.board.finish()
            self.state = GAME_OVER
            self.ended_at = now

    # --- desenho ---
    def draw(self, img, now: float):
        h, w = img.shape[:2]
        ui.panel(img, 0, 0, w, h, alpha=0.25)  # escurece um pouco a camera: frutas aparecem mais

        if len(self.players) == 2:
            cv2.line(img, (w // 2, 60), (w // 2, h), (200, 200, 200), 2)

        for pc in self.pieces:
            if pc.kind in ("half", "drop"):
                draw_piece(img, pc)
        for f in self.fruits:
            draw_fruit(img, f, now)
        for pc in self.pieces:
            if pc.kind in ("text", "miss"):
                draw_piece(img, pc)
        for key, blade in self.blades.items():
            draw_blade(img, blade, now)

        if self.flash > 0:
            ui.panel(img, 0, 0, w, h, ui.WHITE, min(0.8, self.flash * 2.2))

        if self.state == START:
            progress = now - self.start_hold.since if self.start_hold.active else None
            mode = "2 jogadores: cada um no seu lado da tela" if len(self.players) == 2 \
                else f"Fruta perdida ou bomba cortada = -1 vida ({self.players[0].board.max_lives} vidas)"
            draw_start_screen(img, "CORTE NO AR",
                              ["Corte as frutas com um movimento rapido do indicador", mode],
                              "Mostre a MAO ABERTA ou aperte ESPACO", progress,
                              max(p.board.best for p in self.players))
            return

        for p in self.players:
            label = "Pontos" if len(self.players) == 1 else f"J{p.index + 1}"
            draw_hud(img, p.board, p.x1, p.x2, label)
            if len(self.players) == 2 and not p.board.alive and self.state == PLAYING:
                ui.text(img, "FORA", ((p.x1 + p.x2) // 2, h // 2), 2.0, ui.RED, 3, center=True)

        if self.state == GAME_OVER:
            self._draw_game_over(img, now)

    def _draw_game_over(self, img, now: float):
        h, w = img.shape[:2]
        hint = "Mao aberta ou ESPACO joga de novo | ESC sai" if self._can_restart(now) else ""
        if len(self.players) == 1:
            p = self.players[0]
            draw_game_over(img, p.board.score,
                           f"Frutas: {p.sliced}   Maior combo: {p.best_combo}   Recorde: {p.board.best}",
                           hint)
            return
        a, b = (p.board.score for p in self.players)
        title = "EMPATE!" if a == b else f"JOGADOR {1 if a > b else 2} VENCEU!"
        ui.panel(img, 0, 60, w, h, alpha=0.65)
        ui.text(img, title, (w // 2, h // 2 - 110), 1.8, ui.YELLOW, 4, center=True)
        for p in self.players:
            cx = (p.x1 + p.x2) // 2
            ui.text(img, f"J{p.index + 1}: {p.board.score}", (cx, h // 2 - 10), 1.6, ui.WHITE, 3, center=True)
            ui.text(img, f"Frutas {p.sliced} | Combo {p.best_combo}", (cx, h // 2 + 45), 0.8, center=True)
        if hint:
            ui.text(img, hint, (w // 2, h // 2 + 130), 0.9, ui.GREEN, center=True)


# ---------- desenho dos objetos ----------
def _shade(color: Color, k: float) -> Color:
    return tuple(int(max(0, min(255, c * k))) for c in color)


def _mix(a: Color, b: Color, t: float) -> Color:
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def draw_fruit(img, f: Fruit, now: float):
    x, y, r = int(f.x), int(f.y), int(f.r)
    k = f.kind
    cv2.circle(img, (x, y), r + 2, _shade(k.skin, 0.5), -1, cv2.LINE_AA)
    cv2.circle(img, (x, y), r, k.skin, -1, cv2.LINE_AA)
    if k.stripes:
        for off in (-0.5, 0.0, 0.5):
            cv2.ellipse(img, (x, y), (max(2, int(r * (0.25 + abs(off) * 0.9))), r),
                        math.degrees(f.angle), 0, 360, _shade(k.skin, 0.6), 2, cv2.LINE_AA)
    # brilho
    cv2.circle(img, (x - r // 3, y - r // 3), max(2, r // 5), _mix(k.skin, (255, 255, 255), 0.55),
               -1, cv2.LINE_AA)
    sx, sy = math.sin(f.angle), -math.cos(f.angle)
    top = (int(x + sx * r), int(y + sy * r))
    if f.is_bomb:
        fuse = (int(x + sx * r * 1.45), int(y + sy * r * 1.45))
        cv2.line(img, top, fuse, (60, 110, 150), 3, cv2.LINE_AA)
        spark = 4 + int(3 * abs(math.sin(now * 25)))
        cv2.circle(img, fuse, spark + 2, (0, 140, 255), -1, cv2.LINE_AA)
        cv2.circle(img, fuse, spark, (120, 240, 255), -1, cv2.LINE_AA)
        ui.text(img, "X", (x, y), 0.9, ui.RED, 2, center=True)
    else:
        stem = (int(x + sx * r * 1.25), int(y + sy * r * 1.25))
        cv2.line(img, top, stem, (40, 70, 100), 3, cv2.LINE_AA)
        leaf = (int(x + sx * r * 1.1 + sy * -r * 0.3), int(y + sy * r * 1.1 - sx * -r * 0.3))
        cv2.ellipse(img, leaf, (max(3, r // 4), max(2, r // 8)), math.degrees(f.angle) + 30,
                    0, 360, (60, 170, 60), -1, cv2.LINE_AA)


def draw_piece(img, pc: Piece):
    x, y = int(pc.x), int(pc.y)
    if pc.kind == "half":
        r = int(pc.r)
        k = pc.fruit
        cv2.ellipse(img, (x, y), (r, r), pc.angle, 0, 180, _shade(k.skin, 0.6), -1, cv2.LINE_AA)
        cv2.ellipse(img, (x, y), (int(r * 0.9), int(r * 0.9)), pc.angle, 0, 180, k.flesh, -1, cv2.LINE_AA)
    elif pc.kind == "drop":
        cv2.circle(img, (x, y), max(1, int(pc.r * min(1.0, pc.life * 2))), pc.color, -1, cv2.LINE_AA)
    elif pc.kind == "text":
        ui.text(img, pc.text, (x, y), 0.9, pc.color, 2, center=True)
    elif pc.kind == "miss":
        s = 18
        cv2.line(img, (x - s, y - s), (x + s, y + s), ui.RED, 6, cv2.LINE_AA)
        cv2.line(img, (x - s, y + s), (x + s, y - s), ui.RED, 6, cv2.LINE_AA)


def draw_blade(img, blade: Blade, now: float):
    pts = list(blade.trail)
    if len(pts) < 2:
        return
    cutting = blade.cutting
    for i in range(1, len(pts)):
        frac = i / (len(pts) - 1)
        thick = max(1, int((10 if cutting else 3) * frac))
        color = (255, 255, 255) if cutting else (170, 170, 170)
        p1 = (int(pts[i - 1][0]), int(pts[i - 1][1]))
        p2 = (int(pts[i][0]), int(pts[i][1]))
        cv2.line(img, p1, p2, color, thick, cv2.LINE_AA)
    x, y, _ = pts[-1]
    cv2.circle(img, (int(x), int(y)), 6, (255, 255, 255) if cutting else (170, 170, 170), -1, cv2.LINE_AA)


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="corte", description="Jogo: corte as frutas no ar")
    p.add_argument("--jogadores", type=int, default=1, choices=(1, 2),
                   help="2 = tela dividida, um jogador de cada lado")
    p.add_argument("--vidas", type=int, default=3, help="vidas por jogador (padrao 3)")
    p.add_argument("--velocidade", type=float, default=1.0,
                   help="velocidade do jogo (0.7 = mais lento, padrao 1.0)")
    p.add_argument("--bomba-fatal", action="store_true", help="cortar bomba acaba o jogo")
    p.add_argument("--sem-som", action="store_true", help="desliga os efeitos sonoros")
    p.add_argument("--camera", type=int, default=0)
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    sound = SoundFx(enabled=not args.sem_som)
    game = SliceGame(args.jogadores, max(1, args.vidas), max(0.3, args.velocidade),
                     args.bomba_fatal, sound)
    try:
        run_game(game, WINDOW, args.camera, max_hands=2 if args.jogadores == 1 else 4)
    finally:
        sound.close()


if __name__ == "__main__":
    main()
