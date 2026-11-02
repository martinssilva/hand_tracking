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

### Estrutura

```
main.py                  # lançador: python main.py <comando>
apps/
  gesture_game.py        # jogo Imite o Gesto
  theremin.py            # simulador de teremim
  common/
    tracker.py           # HandTracker (MediaPipe) — até 2 mãos, reutilizável
    gestures.py          # dedos esticados/dobrados + reconhecimento de gestos
    draw.py              # texto, painéis, barras, corações, ícone de mão
    music.py             # notas <-> frequências, escalas, afinação
    synth.py             # oscilador com glide/vibrato + saída de áudio (sounddevice)
```

Para criar uma funcionalidade nova: crie `apps/<nome>.py` com uma função `main(argv)`
e registre o comando no dicionário `COMMANDS` em `main.py`.
