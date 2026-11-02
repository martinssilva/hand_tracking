"""
Base comum para os jogos: placar (pontos, vidas e recorde), temporizador de
"segurar", HUD, telas de inicio e de fim de jogo e o laco principal da camera.

Um jogo que usa `run_game` precisa ter:
    process(now, hands, width, height)  -> logica do frame
    draw(img, now)                      -> desenho do frame
    on_key(key, now)                    -> tecla apertada (ESC ja e tratado aqui)
    show_landmarks                      -> atributo/propriedade: desenhar os pontos da mao?
"""
import time
from typing import Optional, Sequence

import cv2

from apps.common import draw as ui


class Scoreboard:
    """Pontos, vidas e recorde (o recorde vale para a sessao)."""

    def __init__(self, lives: int):
        self.max_lives = lives
        self.best = 0
        self.reset()

    def reset(self) -> None:
        self.score = 0
        self.lives = self.max_lives

    def add(self, points: int) -> None:
        self.score += points

    def lose_life(self) -> None:
        self.lives = max(0, self.lives - 1)

    @property
    def alive(self) -> bool:
        return self.lives > 0

    def finish(self) -> None:
        """Chamar no fim de jogo: atualiza o recorde."""
        self.best = max(self.best, self.score)


class HoldTimer:
    """Mede ha quanto tempo uma condicao esta verdadeira sem interrupcao."""

    def __init__(self):
        self.since: Optional[float] = None

    def update(self, now: float, active: bool) -> float:
        """Retorna os segundos seguidos com a condicao ativa (0 se inativa)."""
        if not active:
            self.since = None
            return 0.0
        if self.since is None:   # `is None`: um timestamp 0.0 e valido
            self.since = now
        return now - self.since

    def reset(self) -> None:
        self.since = None

    @property
    def active(self) -> bool:
        return self.since is not None


# ---------- desenho ----------
def draw_hud(img, board: Scoreboard, x1: int = 0, x2: Optional[int] = None,
             label: str = "Pontos") -> None:
    """Faixa do topo com os pontos (esquerda) e os coracoes (direita)."""
    x2 = img.shape[1] if x2 is None else x2
    ui.panel(img, x1, 0, x2, 60)
    ui.text(img, f"{label}: {board.score}", (x1 + 20, 42), 1.0, ui.YELLOW)
    for i in range(board.max_lives):
        ui.heart(img, x2 - 40 - i * 45, 26, 26, filled=i < board.lives)


def draw_start_screen(img, title: str, lines: Sequence[str], hint: str,
                      progress: Optional[float] = None, best: int = 0) -> None:
    h, w = img.shape[:2]
    cx = w // 2
    ui.panel(img, 0, 0, w, h, alpha=0.5)
    ui.text(img, title, (cx, h // 2 - 110), 2.0, ui.YELLOW, 3, center=True)
    for i, line in enumerate(lines):
        ui.text(img, line, (cx, h // 2 - 30 + 45 * i), 0.9, center=True)
    ui.text(img, hint, (cx, h // 2 + 90), 0.9, ui.GREEN, center=True)
    if progress is not None:
        ui.progress_bar(img, cx - 150, h // 2 + 120, 300, 16, progress)
    if best:
        ui.text(img, f"Recorde: {best}", (cx, h - 40), 0.9, ui.YELLOW, center=True)


def draw_game_over(img, score: int, details: str, hint: str = "ESPACO joga de novo | ESC sai",
                   title: str = "FIM DE JOGO", top: int = 60) -> None:
    h, w = img.shape[:2]
    cx = w // 2
    ui.panel(img, 0, top, w, h, alpha=0.65)
    ui.text(img, title, (cx, h // 2 - 90), 2.2, ui.RED, 4, center=True)
    ui.text(img, f"Pontos: {score}", (cx, h // 2), 1.6, ui.YELLOW, 3, center=True)
    if details:
        ui.text(img, details, (cx, h // 2 + 60), 1.0, center=True)
    if hint:
        ui.text(img, hint, (cx, h // 2 + 130), 0.9, ui.GREEN, center=True)


# ---------- laco principal ----------
def run_game(game, window: str, camera: int = 0, max_hands: int = 2) -> None:
    """Camera -> espelho -> tracker -> game.process -> game.draw, ate ESC."""
    # import aqui para os jogos poderem ser importados (e testados) sem mediapipe
    from apps.common.tracker import HandTracker, open_camera

    cap = open_camera(camera)
    tracker = HandTracker(max_hands=max_hands)
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame = cv2.flip(frame, 1)  # espelha: fica natural como um espelho
            now = time.monotonic()
            h, w = frame.shape[:2]

            hands = tracker.process(frame)
            game.process(now, hands, w, h)
            if game.show_landmarks:
                for hand in hands:
                    tracker.draw(frame, hand)
            game.draw(frame, now)
            cv2.imshow(window, frame)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                break
            if key != 255:
                game.on_key(key, now)
            if cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        cap.release()
        tracker.close()
        cv2.destroyAllWindows()
