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

from apps.common import draw as ui
from apps.common.game import (HoldTimer, Scoreboard, draw_game_over, draw_hud,
                              draw_start_screen, run_game)
from apps.common.gestures import GESTURES, classify

WINDOW = "Imite o Gesto"
HOLD_TIME = 0.45        # segundos segurando o gesto certo para valer
START_HOLD_TIME = 1.0   # segundos de mao aberta para comecar
FEEDBACK_TIME = 1.2     # segundos mostrando "Acertou/Errou"
MIN_ROUND_TIME = 2.5    # o tempo por rodada diminui ate esse limite

START, ROUND, FEEDBACK, GAME_OVER = range(4)


def icon_for(gesture, img, cx, cy, size):
    p = gesture.pattern
    ui.hand_icon(img, cx, cy, size, p,
                 ok_sign=gesture.key == "ok",
                 thumb_up=gesture.key == "joinha")


class GestureGame:
    def __init__(self, points_per_hit: int, round_time: float, lives: int,
                 debug: bool = False):
        self.points_per_hit = points_per_hit
        self.base_round_time = round_time
        self.board = Scoreboard(lives)
        self.debug = debug
        self.state = START
        self.start_hold = HoldTimer()   # mao aberta na tela inicial
        self.gesture_hold = HoldTimer() # gesto certo durante a rodada
        self.detected_names = []
        self.reset()

    # ---------- estado ----------
    def reset(self):
        self.board.reset()
        self.hits = 0
        self.target = None
        self.round_start = 0.0
        self.gesture_hold.reset()
        self.feedback_until = 0.0
        self.last_result = None   # (acertou, pontos)

    def round_time(self) -> float:
        return max(MIN_ROUND_TIME, self.base_round_time - 0.15 * self.hits)

    def new_round(self, now: float):
        options = [g for g in GESTURES if g is not self.target]
        self.target = random.choice(options)
        self.round_start = now
        self.gesture_hold.reset()
        self.state = ROUND

    def start(self, now: float):
        self.reset()
        self.new_round(now)

    def finish_round(self, now: float, success: bool):
        if success:
            self.board.add(self.points_per_hit)
            self.hits += 1
            self.last_result = (True, self.points_per_hit)
        else:
            self.board.lose_life()
            self.last_result = (False, 0)
        self.feedback_until = now + FEEDBACK_TIME
        self.state = FEEDBACK

    # ---------- interface do run_game ----------
    @property
    def show_landmarks(self) -> bool:
        return self.debug or self.state in (ROUND, FEEDBACK)

    def process(self, now: float, hands, width: int, height: int):
        detected, names = set(), []
        for hand in hands:
            g = classify(hand.points)
            if g:
                detected.add(g.key)
                names.append(g.name)
        self.detected_names = names
        self.update(now, detected)

    def on_key(self, key: int, now: float):
        if key == ord(" ") and self.state in (START, GAME_OVER):
            self.start(now)

    # ---------- logica por frame ----------
    def update(self, now: float, detected: set):
        if self.state == START:
            # segurar a mao aberta por 1s tambem comeca o jogo
            if self.start_hold.update(now, "aberta" in detected) > START_HOLD_TIME:
                self.start_hold.reset()
                self.start(now)

        elif self.state == ROUND:
            if self.gesture_hold.update(now, self.target.key in detected) >= HOLD_TIME:
                self.finish_round(now, True)
                return
            if now - self.round_start > self.round_time():
                self.finish_round(now, False)

        elif self.state == FEEDBACK:
            if now >= self.feedback_until:
                if not self.board.alive:
                    self.board.finish()
                    self.state = GAME_OVER
                else:
                    self.new_round(now)

    # ---------- desenho ----------
    def draw(self, img, now: float, detected_names=None):
        names = self.detected_names if detected_names is None else detected_names
        h, w = img.shape[:2]
        cx = w // 2

        if self.state == START:
            progress = now - self.start_hold.since if self.start_hold.active else None
            draw_start_screen(img, "IMITE O GESTO",
                              ["Reproduza o simbolo antes do tempo acabar",
                               f"{self.board.max_lives} erros e fim de jogo"],
                              "Mostre a MAO ABERTA ou aperte ESPACO",
                              progress, self.board.best)
            return

        draw_hud(img, self.board)

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
            if self.gesture_hold.active:
                ui.text(img, "Segura...", (20, h - 70), 1.0, ui.GREEN)
                ui.progress_bar(img, 20, h - 55, 250, 14,
                                (now - self.gesture_hold.since) / HOLD_TIME)

        if self.state == FEEDBACK and self.last_result:
            ok, pts = self.last_result
            msg, color = (f"ACERTOU! +{pts}", ui.GREEN) if ok else ("ERROU!", ui.RED)
            ui.text(img, msg, (cx - 130, h // 2), 2.0, color, 4, center=True)

        if self.state == GAME_OVER:
            draw_game_over(img, self.board.score,
                           f"Acertos: {self.hits}   Recorde: {self.board.best}")

        # gesto que esta sendo detectado (ajuda a entender o que a camera ve)
        if self.state != GAME_OVER:
            label = ", ".join(names) if names else "-"
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
    game = GestureGame(args.pontos, args.tempo, args.vidas, debug=args.debug)
    run_game(game, WINDOW, args.camera, max_hands=2)


if __name__ == "__main__":
    main()
