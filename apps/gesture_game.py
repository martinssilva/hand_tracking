"""
Jogo "Imite o Gesto"

Aparece um simbolo de mao na tela e voce tem que reproduzi-lo com a sua mao
antes do tempo acabar. Acertou: ganha pontos. Errou (tempo esgotado): perde
uma vida. Com 3 erros o jogo acaba e mostra a pontuacao.

Uso:
    python main.py gestos [--pontos 10] [--tempo 5] [--vidas 3] [--camera 0]

Teclas: ESPACO comeca/reinicia | ESC sai
"""
import argparse
import random
import time

import cv2

from apps.common import draw as ui
from apps.common.gestures import GESTURES, GESTURES_BY_KEY, classify

WINDOW = "Imite o Gesto"
HOLD_TIME = 0.45        # segundos segurando o gesto certo para valer
FEEDBACK_TIME = 1.2     # segundos mostrando "Acertou/Errou"
MIN_ROUND_TIME = 2.5    # o tempo por rodada diminui ate esse limite

START, ROUND, FEEDBACK, GAME_OVER = range(4)


def icon_for(gesture, img, cx, cy, size):
    p = gesture.pattern
    ui.hand_icon(img, cx, cy, size, p,
                 ok_sign=gesture.key == "ok",
                 thumb_up=gesture.key == "joinha")


class GestureGame:
    def __init__(self, points_per_hit: int, round_time: float, lives: int):
        self.points_per_hit = points_per_hit
        self.base_round_time = round_time
        self.max_lives = lives
        self.best = 0
        self.state = START
        self.start_hold = None
        self.reset()

    # ---------- estado ----------
    def reset(self):
        self.score = 0
        self.hits = 0
        self.lives = self.max_lives
        self.target = None
        self.round_start = 0.0
        self.hold_start = None
        self.feedback_until = 0.0
        self.last_result = None   # (acertou, pontos)

    def round_time(self) -> float:
        return max(MIN_ROUND_TIME, self.base_round_time - 0.15 * self.hits)

    def new_round(self, now: float):
        options = [g for g in GESTURES if g is not self.target]
        self.target = random.choice(options)
        self.round_start = now
        self.hold_start = None
        self.state = ROUND

    def start(self, now: float):
        self.reset()
        self.new_round(now)

    def finish_round(self, now: float, success: bool):
        if success:
            self.score += self.points_per_hit
            self.hits += 1
            self.last_result = (True, self.points_per_hit)
        else:
            self.lives -= 1
            self.last_result = (False, 0)
        self.feedback_until = now + FEEDBACK_TIME
        self.state = FEEDBACK

    # ---------- logica por frame ----------
    def update(self, now: float, detected: set):
        if self.state == START:
            # segurar a mao aberta por 1s tambem comeca o jogo
            if "aberta" in detected:
                if self.start_hold is None:
                    self.start_hold = now
                if now - self.start_hold > 1.0:
                    self.start_hold = None
                    self.start(now)
            else:
                self.start_hold = None

        elif self.state == ROUND:
            if self.target.key in detected:
                if self.hold_start is None:
                    self.hold_start = now
                if now - self.hold_start >= HOLD_TIME:
                    self.finish_round(now, True)
                    return
            else:
                self.hold_start = None
            if now - self.round_start > self.round_time():
                self.finish_round(now, False)

        elif self.state == FEEDBACK:
            if now >= self.feedback_until:
                if self.lives <= 0:
                    self.best = max(self.best, self.score)
                    self.state = GAME_OVER
                else:
                    self.new_round(now)

    # ---------- desenho ----------
    def draw_hud(self, img):
        h, w = img.shape[:2]
        ui.panel(img, 0, 0, w, 60)
        ui.text(img, f"Pontos: {self.score}", (20, 42), 1.0, ui.YELLOW)
        for i in range(self.max_lives):
            ui.heart(img, w - 40 - i * 45, 26, 26, filled=i < self.lives)

    def draw(self, img, now: float, detected_names):
        h, w = img.shape[:2]
        cx = w // 2

        if self.state == START:
            ui.panel(img, 0, 0, w, h, alpha=0.5)
            ui.text(img, "IMITE O GESTO", (cx, h // 2 - 110), 2.0, ui.YELLOW, 3, center=True)
            ui.text(img, "Reproduza o simbolo antes do tempo acabar", (cx, h // 2 - 30), 0.9, center=True)
            ui.text(img, f"{self.max_lives} erros e fim de jogo", (cx, h // 2 + 15), 0.9, center=True)
            ui.text(img, "Mostre a MAO ABERTA ou aperte ESPACO", (cx, h // 2 + 90), 0.9, ui.GREEN, center=True)
            if self.start_hold is not None:
                ui.progress_bar(img, cx - 150, h // 2 + 120, 300, 16, now - self.start_hold)
            if self.best:
                ui.text(img, f"Recorde: {self.best}", (cx, h - 40), 0.9, ui.YELLOW, center=True)
            return

        self.draw_hud(img)

        if self.state in (ROUND, FEEDBACK) and self.target:
            # cartao com o gesto alvo
            card_w, card_h = 260, 300
            x1, y1 = w - card_w - 20, 80
            ui.panel(img, x1, y1, x1 + card_w, y1 + card_h, (40, 40, 40), 0.75)
            icon_for(self.target, img, x1 + card_w // 2, y1 + 140, 180)
            ui.text(img, self.target.name, (x1 + card_w // 2, y1 + card_h - 30), 0.9,
                    ui.YELLOW, center=True)

        if self.state == ROUND:
            elapsed = now - self.round_start
            remaining = 1 - elapsed / self.round_time()
            color = ui.GREEN if remaining > 0.5 else ui.YELLOW if remaining > 0.25 else ui.RED
            ui.progress_bar(img, 20, 72, w - 320, 18, remaining, color)
            if self.hold_start is not None:
                ui.text(img, "Segura...", (20, h - 70), 1.0, ui.GREEN)
                ui.progress_bar(img, 20, h - 55, 250, 14, (now - self.hold_start) / HOLD_TIME)

        if self.state == FEEDBACK and self.last_result:
            ok, pts = self.last_result
            msg, color = (f"ACERTOU! +{pts}", ui.GREEN) if ok else ("ERROU!", ui.RED)
            ui.text(img, msg, (cx - 130, h // 2), 2.0, color, 4, center=True)

        if self.state == GAME_OVER:
            ui.panel(img, 0, 60, w, h, alpha=0.65)
            ui.text(img, "FIM DE JOGO", (cx, h // 2 - 90), 2.2, ui.RED, 4, center=True)
            ui.text(img, f"Pontos: {self.score}", (cx, h // 2), 1.6, ui.YELLOW, 3, center=True)
            ui.text(img, f"Acertos: {self.hits}   Recorde: {self.best}", (cx, h // 2 + 60), 1.0, center=True)
            ui.text(img, "ESPACO joga de novo | ESC sai", (cx, h // 2 + 130), 0.9, ui.GREEN, center=True)

        # gesto que esta sendo detectado (ajuda a entender o que a camera ve)
        if self.state != GAME_OVER:
            label = ", ".join(detected_names) if detected_names else "-"
            ui.text(img, f"Detectado: {label}", (20, h - 20), 0.7)


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="gestos", description="Jogo: imite o gesto da tela")
    p.add_argument("--pontos", type=int, default=10, help="pontos por acerto (padrao 10)")
    p.add_argument("--tempo", type=float, default=5.0, help="segundos por rodada (padrao 5)")
    p.add_argument("--vidas", type=int, default=3, help="erros ate o fim de jogo (padrao 3)")
    p.add_argument("--camera", type=int, default=0, help="indice da camera (padrao 0)")
    p.add_argument("--debug", action="store_true", help="desenha os landmarks da mao")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    # import aqui para o --help funcionar mesmo sem mediapipe instalado
    from apps.common.tracker import HandTracker, open_camera

    cap = open_camera(args.camera)
    tracker = HandTracker(max_hands=2)
    game = GestureGame(args.pontos, args.tempo, args.vidas)

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame = cv2.flip(frame, 1)  # espelha: fica natural como um espelho
            now = time.monotonic()

            hands = tracker.process(frame)
            detected = set()
            names = []
            for hand in hands:
                g = classify(hand.points)
                if g:
                    detected.add(g.key)
                    names.append(g.name)
                if args.debug or game.state in (ROUND, FEEDBACK):
                    tracker.draw(frame, hand)

            game.update(now, detected)
            game.draw(frame, now, names)
            cv2.imshow(WINDOW, frame)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                break
            if key == ord(" ") and game.state in (START, GAME_OVER):
                game.start(now)
            if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        cap.release()
        tracker.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
