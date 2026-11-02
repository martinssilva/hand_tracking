"""
Reconhecimento de gestos a partir dos 21 landmarks do MediaPipe.

Este modulo NAO depende do mediapipe: recebe uma lista de 21 pontos (x, y)
normalizados (0..1), o que facilita testar e reutilizar em outros scripts.

Indices dos landmarks:
    0 punho | 1-4 polegar | 5-8 indicador | 9-12 medio | 13-16 anelar | 17-20 minimo
"""
import math
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence, Tuple

Point = Tuple[float, float]

WRIST = 0
THUMB_IP, THUMB_TIP = 3, 4
INDEX_MCP, INDEX_TIP = 5, 8
MIDDLE_MCP = 9

# (ponta, articulacao PIP) de cada dedo, exceto o polegar
_FINGER_JOINTS = ((8, 6), (12, 10), (16, 14), (20, 18))

FINGER_NAMES = ("polegar", "indicador", "medio", "anelar", "minimo")


def _dist(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def palm_size(pts: Sequence[Point]) -> float:
    """Distancia punho -> base do dedo medio. Usada como escala da mao."""
    return max(_dist(pts[WRIST], pts[MIDDLE_MCP]), 1e-6)


def fingers_extended(pts: Sequence[Point]) -> Tuple[bool, bool, bool, bool, bool]:
    """
    Retorna (polegar, indicador, medio, anelar, minimo) -> True se esticado.

    Usa distancias relativas ao punho em vez de comparar so o eixo Y, por isso
    funciona com a mao inclinada ou de lado.
    """
    wrist = pts[WRIST]
    palm = palm_size(pts)

    # Polegar: esticado se a ponta se afasta do centro da palma (base do medio)
    # mais do que a articulacao IP, e se nao esta "deitado" sobre o indicador.
    thumb = (
        _dist(pts[THUMB_TIP], pts[MIDDLE_MCP]) > _dist(pts[THUMB_IP], pts[MIDDLE_MCP]) * 1.1
        and _dist(pts[THUMB_TIP], pts[INDEX_MCP]) > 0.5 * palm
    )

    others = [
        _dist(wrist, pts[tip]) > _dist(wrist, pts[pip]) * 1.12
        for tip, pip in _FINGER_JOINTS
    ]
    return (thumb, *others)


# Padrao = (polegar, indicador, medio, anelar, minimo); None = tanto faz
Pattern = Tuple[Optional[bool], Optional[bool], Optional[bool], Optional[bool], Optional[bool]]


@dataclass(frozen=True)
class Gesture:
    key: str
    name: str                      # texto mostrado na tela (sem acentos: o OpenCV nao desenha)
    pattern: Pattern
    extra: Optional[Callable[[Sequence[Point]], bool]] = field(default=None, compare=False)

    def matches(self, pts: Sequence[Point], fingers=None) -> bool:
        fingers = fingers if fingers is not None else fingers_extended(pts)
        for want, got in zip(self.pattern, fingers):
            if want is not None and want != got:
                return False
        return self.extra(pts) if self.extra else True


def _thumb_pointing_up(pts: Sequence[Point]) -> bool:
    # y cresce para baixo na imagem: ponta do polegar acima da base do indicador
    return pts[THUMB_TIP][1] < pts[INDEX_MCP][1] - 0.3 * palm_size(pts)


def _thumb_touches_index(pts: Sequence[Point]) -> bool:
    return _dist(pts[THUMB_TIP], pts[INDEX_TIP]) < 0.35 * palm_size(pts)


_ = None  # atalho para "tanto faz"

GESTURES = (
    # OK vem primeiro: o polegar encostado no indicador confunde a deteccao de dedos
    Gesture("ok",         "OK",           (_, _, True, True, True), _thumb_touches_index),
    Gesture("punho",      "Punho",        (False, False, False, False, False)),
    Gesture("aberta",     "Mao aberta",   (True, True, True, True, True)),
    Gesture("joinha",     "Joinha",       (True, False, False, False, False), _thumb_pointing_up),
    Gesture("apontar",    "Apontar",      (_, True, False, False, False)),
    Gesture("paz",        "Paz (V)",      (_, True, True, False, False)),
    Gesture("tres",       "Tres dedos",   (_, True, True, True, False)),
    Gesture("rock",       "Rock",         (_, True, False, False, True)),
    Gesture("hangloose",  "Hang loose",   (True, False, False, False, True)),
)

GESTURES_BY_KEY = {g.key: g for g in GESTURES}


def classify(pts: Sequence[Point]) -> Optional[Gesture]:
    """Retorna o primeiro gesto conhecido que bate com a mao, ou None."""
    fingers = fingers_extended(pts)
    for g in GESTURES:
        if g.matches(pts, fingers):
            return g
    return None
