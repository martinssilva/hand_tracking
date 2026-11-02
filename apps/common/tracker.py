"""Wrapper fino em volta do MediaPipe Hands, reutilizavel por todos os scripts."""
from dataclasses import dataclass
from typing import List, Tuple

import cv2
import mediapipe as mp


@dataclass
class Hand:
    points: List[Tuple[float, float]]   # 21 pontos normalizados (0..1)
    label: str                          # "Left" / "Right" (segundo o MediaPipe)
    score: float
    raw: object                         # landmarks originais (para desenhar)

    def pixel(self, idx: int, width: int, height: int) -> Tuple[int, int]:
        x, y = self.points[idx]
        return int(x * width), int(y * height)


class HandTracker:
    def __init__(self, max_hands: int = 2, detection_confidence: float = 0.7,
                 tracking_confidence: float = 0.6):
        self._mp_hands = mp.solutions.hands
        self._drawing = mp.solutions.drawing_utils
        self._hands = self._mp_hands.Hands(
            max_num_hands=max_hands,
            min_detection_confidence=detection_confidence,
            min_tracking_confidence=tracking_confidence,
        )

    def process(self, frame_bgr) -> List[Hand]:
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        result = self._hands.process(rgb)
        hands: List[Hand] = []
        if not result.multi_hand_landmarks:
            return hands
        handedness = result.multi_handedness or []
        for i, lm in enumerate(result.multi_hand_landmarks):
            label, score = "?", 0.0
            if i < len(handedness):
                c = handedness[i].classification[0]
                label, score = c.label, c.score
            hands.append(Hand([(p.x, p.y) for p in lm.landmark], label, score, lm))
        return hands

    def draw(self, frame, hand: Hand) -> None:
        self._drawing.draw_landmarks(frame, hand.raw, self._mp_hands.HAND_CONNECTIONS)

    def close(self) -> None:
        self._hands.close()


def open_camera(index: int = 0, width: int = 1280, height: int = 720):
    cap = cv2.VideoCapture(index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    if not cap.isOpened():
        raise SystemExit(f"Nao foi possivel abrir a camera {index}. Tente --camera 1")
    return cap
