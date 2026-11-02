"""Helpers de desenho com OpenCV (texto com contorno, paineis, icones)."""
from typing import Optional, Sequence, Tuple

import cv2
import numpy as np

Color = Tuple[int, int, int]  # BGR

WHITE: Color = (255, 255, 255)
BLACK: Color = (0, 0, 0)
GREEN: Color = (80, 220, 100)
RED: Color = (70, 70, 235)
YELLOW: Color = (40, 210, 255)
SKIN: Color = (150, 190, 235)
SKIN_DARK: Color = (90, 130, 180)

FONT = cv2.FONT_HERSHEY_DUPLEX


def text(img, msg: str, org, scale: float = 1.0, color: Color = WHITE,
         thickness: int = 2, center: bool = False) -> None:
    """Texto com contorno preto, legivel sobre qualquer fundo."""
    if center:
        (w, h), _ = cv2.getTextSize(msg, FONT, scale, thickness)
        org = (int(org[0] - w / 2), int(org[1] + h / 2))
    # contorno desenhado com deslocamentos (e nao com traco mais grosso), para o
    # contorno ter exatamente a mesma largura do texto
    r = max(1, thickness // 2 + 1)
    for dx in (-r, 0, r):
        for dy in (-r, 0, r):
            if dx or dy:
                cv2.putText(img, msg, (org[0] + dx, org[1] + dy), FONT, scale, BLACK,
                            thickness, cv2.LINE_AA)
    cv2.putText(img, msg, org, FONT, scale, color, thickness, cv2.LINE_AA)


def panel(img, x1: int, y1: int, x2: int, y2: int, color: Color = BLACK,
          alpha: float = 0.55) -> None:
    """Retangulo semitransparente."""
    h, w = img.shape[:2]
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return
    roi = img[y1:y2, x1:x2]
    overlay = roi.copy()
    overlay[:] = color
    cv2.addWeighted(overlay, alpha, roi, 1 - alpha, 0, roi)


def progress_bar(img, x: int, y: int, w: int, h: int, frac: float,
                 color: Color = GREEN, bg: Color = (60, 60, 60)) -> None:
    frac = min(max(frac, 0.0), 1.0)
    cv2.rectangle(img, (x, y), (x + w, y + h), bg, -1)
    if frac > 0:
        cv2.rectangle(img, (x, y), (x + int(w * frac), y + h), color, -1)
    cv2.rectangle(img, (x, y), (x + w, y + h), WHITE, 1)


def heart(img, cx: int, cy: int, size: int, filled: bool = True) -> None:
    """Coracao desenhado com dois circulos + triangulo."""
    color = RED if filled else (90, 90, 90)
    r = size // 2
    cv2.circle(img, (cx - r // 2 - 1, cy), r // 2 + 2, color, -1, cv2.LINE_AA)
    cv2.circle(img, (cx + r // 2 + 1, cy), r // 2 + 2, color, -1, cv2.LINE_AA)
    pts = [(cx - r - 2, cy + 2), (cx + r + 2, cy + 2), (cx, cy + r + 4)]
    cv2.fillPoly(img, [np.array(pts)], color, cv2.LINE_AA)


def hand_icon(img, cx: int, cy: int, size: int,
              fingers: Sequence[Optional[bool]], ok_sign: bool = False,
              thumb_up: bool = False) -> None:
    """
    Desenha uma mao esquematica.

    fingers = (polegar, indicador, medio, anelar, minimo); True = esticado,
    False/None = dobrado. ok_sign desenha o circulo do gesto OK; thumb_up desenha
    o polegar apontando para cima (joinha).
    """
    s = size / 100.0
    t = max(int(14 * s), 3)                       # espessura dos dedos
    palm_w, palm_h = int(56 * s), int(50 * s)
    px1, py1 = cx - palm_w // 2, cy - palm_h // 2 + int(10 * s)
    px2, py2 = px1 + palm_w, py1 + palm_h

    # Dedos (indicador -> minimo), da esquerda para a direita
    lengths = (42, 47, 43, 34)
    gap = palm_w / 4
    for i, ext in enumerate(fingers[1:]):
        fx = int(px1 + gap * (i + 0.5))
        top = py1 - int(lengths[i] * s) if ext else py1 + int(4 * s)
        if ok_sign and i == 0:
            continue
        cv2.line(img, (fx, py1 + t // 2), (fx, top), SKIN_DARK, t + 4, cv2.LINE_AA)
        cv2.line(img, (fx, py1 + t // 2), (fx, top), SKIN, t, cv2.LINE_AA)

    # Palma
    cv2.rectangle(img, (px1 - 2, py1 - 2), (px2 + 2, py2 + 2), SKIN_DARK, -1)
    cv2.rectangle(img, (px1, py1), (px2, py2), SKIN, -1)
    # punho/pulso
    cv2.rectangle(img, (px1 + int(8 * s), py2), (px2 - int(8 * s), py2 + int(18 * s)), SKIN_DARK, -1)

    # Polegar
    base = (px1, py2 - int(14 * s))
    if ok_sign:
        ring_c = (px1 + int(4 * s), py1 - int(16 * s))
        r = int(16 * s)
        cv2.circle(img, ring_c, r, SKIN_DARK, t + 4, cv2.LINE_AA)
        cv2.circle(img, ring_c, r, SKIN, t, cv2.LINE_AA)
        return
    if thumb_up:
        tip = (px1 - int(6 * s), py1 - int(42 * s))
    elif fingers[0]:
        tip = (px1 - int(34 * s), py1 - int(8 * s))
    else:
        tip = (px1 + int(26 * s), py1 + int(18 * s))
    cv2.line(img, base, tip, SKIN_DARK, t + 4, cv2.LINE_AA)
    cv2.line(img, base, tip, SKIN, t, cv2.LINE_AA)
