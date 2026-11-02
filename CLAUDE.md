# CLAUDE.md

Guia para o Claude (e para pessoas) trabalharem neste repositório.

## O projeto

Funcionalidades interativas controladas pelas mãos via webcam, em Python:
**OpenCV** (câmera e desenho), **MediaPipe Hands** (21 pontos por mão) e
**sounddevice** (áudio). O script original (`hand_tracking.py`) controla o
mouse com o indicador. Por cima dele foi criada uma estrutura de "apps", em que
cada funcionalidade é um script separado e roda por um comando no terminal.

Idioma do projeto: **português** (código comentado, mensagens, commits, README).

## Estado das branches (importante)

A `master` ainda **não tem** o código novo. As funcionalidades estão em
branches **empilhadas**: cada uma parte da anterior e contém tudo dela.

```
master
 └─ claude/manual-tracking-game-3j9ia1   lançador + apps/common + jogo "gestos"
     └─ claude/teremim                   + teremim, music.py, synth.py
         └─ claude/circulo-cromatico     + círculo cromático, PolySynth, acordes
```

- Para ter tudo, use a `claude/circulo-cromatico`. Fazer o merge dela na
  `master` traz as três.
- Uma funcionalidade nova deve partir da branch mais recente, hoje a
  `claude/circulo-cromatico`, até que tudo seja mergeado na `master`.
- A correção do contorno de texto em `draw.text` está só a partir da
  `claude/teremim`. A branch do jogo ainda tem a versão antiga.

## Como rodar

```
python -m venv venv && venv\Scripts\activate      # Windows (ambiente do usuário)
pip install opencv-python mediapipe pyautogui sounddevice

python main.py                 # lista os comandos
python main.py <comando> --help
python main.py gestos          # jogo Imite o Gesto
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
  theremin.py            # "teremim": mão direita = nota (altura), esquerda = volume
  color_wheel.py         # "circulo": 12 notas coloridas em anéis; pinça/toque; acordes
  common/
    tracker.py           # HandTracker (MediaPipe, até 2 mãos), Hand, open_camera()
    gestures.py          # fingers_extended(), Gesture, GESTURES, classify(), palm_size()
    draw.py              # text() com contorno, panel(), progress_bar(), heart(), hand_icon()
    music.py             # midi<->freq, note_name(), parse_note(), SCALES, snap_to_scale(),
                         # chord_name(), triad()
    synth.py             # Oscillator (glide/vibrato), PolySynth (vozes), AudioOutput
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
5. Documente no README: tabela de comandos, uma seção da funcionalidade e a
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
  mesma espessura do texto. Um traço mais grosso deixa o contorno mais largo e
  cria um texto "fantasma".
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
  - Na `master`, o `.gitignore` também está em UTF-16 e por isso é ignorado
    pelo Git. Nas branches novas ele já foi convertido para UTF-8. Não
    comite `__pycache__`.

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
- **Ambiente:** `pip install opencv-python-headless numpy`. O mediapipe e o
  PortAudio não estão disponíveis no ambiente do Claude.

Ainda não existe pasta de testes no repositório (veja o PLAN.md).
