Criar e ativar um ambiente virtual (recomendado)

Isso evita conflitos entre bibliotecas:

python -m venv venv


Ativar:

Windows (CMD/PowerShell):

venv\Scripts\activate

Instalar as bibliotecas necessárias

Agora sim usar o pip dentro do ambiente:

pip install opencv-python mediapipe pyautogui


📌 Explicando:
.
opencv-python → captura de vídeo e processamento de imagem.

mediapipe → reconhecimento da mão.

pyautogui → controla o mouse/teclado.



no requirements.txt tem varios arquivos, mas instalei só esses três usando o comando acima.


---

# Funcionalidades (comandos)

Todas as funcionalidades ficam na pasta `apps/` e rodam por um único lançador:

```
python main.py              # lista os comandos disponíveis
python main.py <comando>    # roda a funcionalidade
python main.py <comando> --help
```

| Comando  | O que faz |
|----------|-----------|
| `gestos` | Jogo **Imite o Gesto**: aparece um símbolo de mão e você tem que repetir com a sua mão antes do tempo acabar. Acertou = ganha pontos; 3 erros = fim de jogo e mostra a pontuação. |
| `teremim` | **Simulador de teremim**: mão direita controla a nota, mão esquerda o volume. |
| `circulo` | **Círculo cromático**: toque nas fatias coloridas para tocar notas e acordes. |
| `mouse`  | Script original (`hand_tracking.py`): controla o mouse com o indicador. |

### Jogo "Imite o Gesto"

```
python main.py gestos                       # padrão: 10 pontos por acerto, 5s por rodada, 3 vidas
python main.py gestos --pontos 50 --tempo 4 --vidas 5 --camera 1
```

- Comece mostrando a **mão aberta** por 1 segundo (ou apertando ESPAÇO).
- Segure o gesto certo por ~0,5s para valer. O tempo por rodada diminui conforme você acerta.
- Gestos: OK, Punho, Mão aberta, Joinha, Apontar, Paz (V), Três dedos, Rock, Hang loose.
- No canto inferior aparece o gesto que a câmera está detectando (ajuda a entender erros).
- ESC sai.

### Simulador de Teremim

Precisa do pacote de áudio: `pip install sounddevice`

```
python main.py teremim                                  # 2 oitavas a partir de C3, glissando livre
python main.py teremim --escala pentatonica --nota-base A2 --oitavas 3
python main.py teremim --timbre seno --vibrato
```

- **Mão direita** (lado direito da tela): a altura da ponta do indicador define a nota
  (mais alto = mais agudo). As linhas mostram onde fica cada nota.
- **Punho na mão direita** = silêncio. Assim dá para separar uma nota da outra.
- **Mão esquerda** (lado esquerdo): mais alta = mais volume. Sem ela, o volume fica fixo (`--volume`).
- Escalas: `livre` (contínuo, como o teremim real), `cromatica`, `maior`, `menor`,
  `pentatonica`, `blues`. Nas escalas a nota "gruda" na mais próxima, o que facilita tocar afinado.
- Timbres: `teremim`, `seno`, `triangulo`, `quadrada`.
- Na tela: nome da nota, frequência, afinador em cents e um mini osciloscópio.
- Teclas: **Q** troca a escala, **W** troca o timbre, **V** liga/desliga o vibrato,
  **H** mostra os pontos da mão, **ESC** sai.

### Círculo Cromático

Também precisa do `sounddevice`.

```
python main.py circulo                                   # pinça, ordem cromática, 2 oitavas
python main.py circulo --ordem quintas --acorde diatonico --escala maior --tonica G
python main.py circulo --modo toque --decaimento 1.5     # só encostar; som some como piano
```

- 12 fatias coloridas (as cores dão a volta no arco-íris). Cada **anel** é uma oitava, e o de dentro é o mais grave.
- **Modo `pinca`** (padrão): encoste o polegar no indicador em cima da nota. Ela soa enquanto a pinça
  estiver fechada. Arrastar a pinça para outra fatia troca a nota.
- **Modo `toque`**: basta a ponta do indicador estar em cima da fatia.
- **Duas mãos** tocam ao mesmo tempo, e o centro do círculo mostra o nome do acorde formado (ex.: "Do maior").
- **Acordes** (`--acorde`): `nota` toca só a nota; `maior` e `menor` tocam a tríade. `diatonico` monta o acorde
  da escala escolhida: em Dó maior, Ré vira Ré menor e Sol vira Sol maior.
- **Ordem** (`--ordem`): `cromatica` (Dó, Dó#, Ré…) ou `quintas` (Dó, Sol, Ré, Lá…).
  No círculo das quintas, os acordes que combinam ficam vizinhos.
- **Escala** (`--escala` + `--tonica`): escurece as notas que ficam fora da escala.
- **`--decaimento`**: tempo para a nota sumir mesmo segurada (0 = sustenta).
- Teclas: **M** modo, **Q** ordem, **A** acorde, **E** escala, **W** timbre, **H** pontos da mão, **ESC** sai.

### Estrutura

```
main.py                  # lançador: python main.py <comando>
apps/
  gesture_game.py        # jogo Imite o Gesto
  theremin.py            # simulador de teremim
  color_wheel.py         # círculo cromático musical
  common/
    tracker.py           # HandTracker (MediaPipe) — até 2 mãos, reutilizável
    gestures.py          # dedos esticados/dobrados + reconhecimento de gestos
    draw.py              # texto, painéis, barras, corações, ícone de mão
    music.py             # notas <-> frequências, escalas, nomes de acordes, tríades
    synth.py             # oscilador (glide/vibrato), PolySynth (várias notas) e saída de áudio
```

Para criar uma funcionalidade nova: crie `apps/<nome>.py` com uma função `main(argv)`
e registre o comando no dicionário `COMMANDS` em `main.py`.
