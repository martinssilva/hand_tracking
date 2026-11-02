# CLAUDE.md

Guia para o Claude (e para pessoas) trabalharem neste repositório.

## O projeto

Funcionalidades interativas controladas pelas mãos via webcam, em Python:
**OpenCV** (câmera e desenho), **MediaPipe Hands** (21 pontos por mão) e
**sounddevice** (áudio). O script original (`hand_tracking.py`) controla o
mouse com o indicador. Por cima dele foi criada uma estrutura de "apps", em que
cada funcionalidade é um script separado e roda por um comando no terminal.

Idioma do projeto: **português** (código comentado, mensagens, commits, README).

## Branches e PRs

A `master` tem todo o código (jogo de gestos, teremim e círculo cromático,
mergeados nos PRs #1 e #4).

- Cada funcionalidade nova fica numa branch própria criada a partir da
  `master` e entra por PR direto para a `master`.
- **Evite PRs empilhados** (base = outra branch de feature). No PR #2 e no #3
  o merge foi feito na branch de base e não na `master`, porque as branches
  não foram apagadas e o GitHub não mudou a base sozinho. Foi preciso um PR
  extra (#4) para corrigir.
- Se empilhar for inevitável, avise o usuário para mergear em ordem e apagar
  a branch depois de cada merge, ou para mudar a base do PR seguinte para a
  `master`.

## Como rodar

```
python -m venv venv && venv\Scripts\activate      # Windows (ambiente do usuário)
pip install opencv-python mediapipe pyautogui sounddevice

python main.py                 # lista os comandos
python main.py <comando> --help
python main.py gestos          # jogo Imite o Gesto
python main.py corte           # jogo Corte no Ar (cortar frutas; 1 ou 2 jogadores)
python main.py teremim         # simulador de teremim
python main.py circulo         # círculo cromático musical
python main.py mouse           # script original (hand_tracking.py)
```

- O usuário roda no **Windows**, com webcam.
- O código usa a API `mp.solutions.hands` do MediaPipe, que existe na
  versão 0.10.14 (a do `requirements.txt`). Versões mais novas do MediaPipe
  podem remover essa API.

## Estrutura

```
main.py                  # lançador: COMMANDS = {comando: (módulo, descrição)}
hand_tracking.py         # script original (controle do mouse), roda no import
apps/
  gesture_game.py        # "gestos": imite o gesto da tela; acerto = pontos, 3 erros = fim
  slice_game.py          # "corte": frutas lançadas, o indicador corta (rápido); combos, bombas, 2 jogadores
  theremin.py            # "teremim": mão direita = nota (altura), esquerda = volume
  color_wheel.py         # "circulo": 12 notas coloridas em anéis; pinça/toque; acordes
  common/
    tracker.py           # HandTracker (MediaPipe, até 2 mãos), Hand, open_camera()
    game.py              # Scoreboard, HoldTimer, draw_hud/start/game_over, run_game()
    gestures.py          # fingers_extended(), Gesture, GESTURES, classify(), palm_size()
    draw.py              # text() com contorno, panel(), progress_bar(), heart(), hand_icon()
    music.py             # midi<->freq, note_name(), parse_note(), SCALES, snap_to_scale(),
                         # chord_name(), triad()
    synth.py             # Oscillator (glide/vibrato), PolySynth (vozes), AudioOutput
tests/                   # pytest, sem câmera: helpers.py tem as mãos sintéticas
```

`gestures.py` e `music.py` **não importam** mediapipe nem OpenCV. O
`synth.py` só carrega o `sounddevice` dentro de `AudioOutput`.

## Como adicionar uma funcionalidade

1. Crie `apps/<nome>.py` com `parse_args(argv)` e `main(argv=None)`.
2. Registre em `COMMANDS` no `main.py`: `"comando": ("apps.<nome>", "descrição")`.
3. Importe `tracker` e `AudioOutput` **dentro de `main()`**. Assim o `--help`
   e os testes funcionam sem câmera e sem mediapipe.
4. Deixe a lógica numa classe com `update(...)` (estado por frame) e
   `draw(img)`. Mapeamentos e geometria ficam em funções puras, para poder
   testar.
5. **Jogos** usam `apps/common/game.py`:
   - `Scoreboard` para pontos, vidas e recorde;
   - `HoldTimer` para "segure X segundos";
   - `draw_hud`, `draw_start_screen` e `draw_game_over` para as telas;
   - `run_game(jogo, janela, camera)` para o laço da câmera. O jogo precisa ter
     `process(now, hands, w, h)`, `draw(img, now)`, `on_key(key, now)` e
     `show_landmarks`.
   - Para manter o padrão, os jogos começam com a mão aberta segurada por 1s
     ou com ESPAÇO.
6. Escreva os testes em `tests/test_<nome>.py`, usando as mãos sintéticas de
   `tests/helpers.py`.
7. Documente no README: tabela de comandos, uma seção da funcionalidade e a
   árvore de estrutura.

## Convenções e armadilhas

- **Espelhar o frame:** `cv2.flip(frame, 1)` logo após ler a câmera. Todos os
  apps trabalham na imagem espelhada. "Mão direita" significa o lado direito
  da tela, e não o `label` do MediaPipe, que fica invertido com o espelho.
- **Coordenadas:** `Hand.points` são `(x, y)` normalizados entre 0 e 1, com y
  crescendo para baixo. Para pixels, multiplique pela largura e altura do frame.
- **Escala da mão:** compare distâncias em relação a `palm_size(pts)`
  (punho → base do dedo médio), nunca em pixels absolutos. Assim funciona
  perto ou longe da câmera.
- **Dedos esticados:** `fingers_extended` usa distâncias ao punho, e não só o
  eixo Y, para funcionar com a mão inclinada. O polegar é medido em relação à
  base do dedo médio (ponto 9).
- **Sem acentos no texto da tela:** o `cv2.putText` não desenha acentos. Escreva
  "Mao", "Tres", "Do#". Acentos podem aparecer no README e nos comentários.
- **Contorno de texto:** `draw.text` desenha o contorno com deslocamentos e a
  mesma espessura do texto. Não volte a usar um traço mais grosso: ele deixa o
  contorno mais largo e cria um texto "fantasma".
- **Tempo:** compare timestamps com `is None`, nunca com `x or now`, porque
  0.0 é falsy. Esse bug já aconteceu no jogo.
- **Áudio:** a thread da câmera só altera `target_freq` e `target_amp`
  (Oscillator) ou chama `note_on/note_off` (PolySynth). O callback de áudio
  faz as transições suaves. Não gere áudio na thread da câmera.
- **Histerese** contra tremida do tracking:
  - Pinça: liga em 0.30 e desliga em 0.45 × palma (`color_wheel.py`).
  - Troca de nota nas escalas: `SNAP_HYSTERESIS` (`theremin.py`).
  - Gesto: precisa ser segurado por `HOLD_TIME` (`gesture_game.py`).
- **Encoding:**
  - `requirements.txt` está em **UTF-16** e o `pip` lê assim mesmo. Não
    reescreva sem necessidade.
  - O `.gitignore` já foi convertido para UTF-8 (antes, em UTF-16, o Git o
    ignorava). Mantenha em UTF-8 e não comite `__pycache__`.

## Testes sem câmera

O ambiente do Claude não tem webcam, mediapipe nem placa de som. Para validar:

- **Gestos:** monte 21 pontos sintéticos (mão de pé, dedos esticados ou
  dobrados) e chame `classify()` ou `fingers_extended()`.
- **Mãos falsas:** `SimpleNamespace(points=[...], label="Right")` serve como
  `Hand` em `update()`.
- **Som:**
  - `Oscillator.render(n)` e `PolySynth.render(n)` geram amostras sem áudio.
  - Confira a frequência com FFT e procure estalos pelo maior salto entre
    amostras.
  - Grave um `.wav` com o módulo `wave` para ouvir.
- **Telas:** chame `draw(img)` num `np.full((720, 1280, 3), 70, np.uint8)` e
  salve com `cv2.imwrite`.
- **Ambiente:** `pip install opencv-python-headless numpy pytest`. O mediapipe e o
  PortAudio não estão disponíveis no ambiente do Claude.
- **Rodar:** `python -m pytest tests`. Rode sempre antes de comitar.
- **Refatoração sem mudar comportamento:** salve as telas antes da mudança
  com um roteiro fixo (`random.seed`, tempos fixos) e compare pixel a pixel
  depois. Foi assim que o `gesture_game.py` passou para o `game.py`.

## Originalidade

Jogos podem ser do mesmo **gênero** de jogos conhecidos, mas não recriações
deles: nada de nome, marca, arte ou interface copiados. Por exemplo, o pedido
de um "fruit ninja" virou o "Corte no Ar" (`corte`), um jogo original de
cortar frutas no padrão dos nossos jogos.
