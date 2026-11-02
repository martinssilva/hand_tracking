# PLAN.md

Roteiro das funcionalidades de hand tracking: o que foi feito, o que vem a
seguir e as pendências. Detalhes técnicos estão no CLAUDE.md.

## Visão

Uma coleção de experiências controladas pelas mãos via webcam. Cada uma é um
script separado e roda com `python main.py <comando>`. Todas compartilham o
tracking, o reconhecimento de gestos, o desenho e o áudio em `apps/common/`.

## Feito

| # | Funcionalidade | Comando | PR | Status |
|---|---|---|---|---|
| 0 | Controle do mouse (original) | `mouse` | — | na `master` |
| 1 | Lançador + módulos comuns | `python main.py` | #1 | na `master` |
| 2 | Jogo "Imite o Gesto" | `gestos` | #1 | na `master`, testado sem câmera |
| 3 | Simulador de teremim | `teremim` | #2 → #4 | na `master`, testado sem câmera |
| 4 | Círculo cromático musical | `circulo` | #3 → #4 | na `master`, testado sem câmera |
| 5 | Base de jogo comum + testes | `python -m pytest tests` | `claude/fruit-ninja` | 34 testes passando |
| 6 | Jogo "Corte no Ar" (estilo fruit ninja) | `corte` | `claude/fruit-ninja` | testado sem câmera |

### 1. Lançador e módulos comuns
- `main.py` lista os comandos e repassa os argumentos para cada app.
- `apps/common/tracker.py`: acompanha até 2 mãos.
- `apps/common/gestures.py`: reconhece 9 gestos (OK, Punho, Mão aberta,
  Joinha, Apontar, Paz, Três dedos, Rock, Hang loose), mesmo com a mão
  inclinada.
- `apps/common/draw.py`: textos com contorno, painéis, barras, corações e
  ícone de mão desenhado com formas.

### 2. Jogo "Imite o Gesto" (`gestos`)
- Um cartão mostra o gesto, que precisa ser repetido antes do tempo acabar.
- O gesto certo precisa ser segurado por 0,45s para valer.
- Acerto soma pontos (`--pontos`, padrão 10). O tempo de cada rodada cai a
  cada acerto, de 5s até no mínimo 2,5s.
- 3 erros (`--vidas`) encerram o jogo, que mostra pontos, acertos e o recorde
  da sessão.
- Começa com a mão aberta segurada por 1s ou com ESPAÇO.

### 3. Teremim (`teremim`)
- Mão direita: a altura do indicador define a nota. Punho silencia.
- Mão esquerda: a altura da mão define o volume. Sem ela, o volume é fixo.
- Escalas: livre (contínua), cromática, maior, menor, pentatônica e blues,
  com histerese para a nota não ficar pulando.
- Timbres: teremim, seno, triângulo e quadrada. Vibrato opcional.
- Na tela: afinador em cents e mini osciloscópio.
- Base de áudio: `music.py` e `synth.py`, com glissando logarítmico e sem
  estalos.

### 4. Círculo cromático (`circulo`)
- 12 fatias coloridas em arco-íris. Cada anel é uma oitava (`--aneis` 1 a 4).
- Modos de tocar: pinça (padrão, com histerese) ou toque.
- Duas mãos tocam juntas, e o centro do círculo mostra o nome do acorde.
- Modos de acorde: nota, maior, menor e diatônico (acorde montado dentro da
  escala escolhida).
- Ordem cromática ou do círculo das quintas. Destaque da escala com
  `--escala` e `--tonica`.
- `PolySynth`: até 10 vozes, cortando a mais antiga quando falta voz, com
  decaimento opcional (som tipo piano) e saturação suave.

### 5. Base de jogo comum (`apps/common/game.py`) e testes (`tests/`)
- `Scoreboard` (pontos, vidas, recorde), `HoldTimer`, HUD, telas de início e
  fim de jogo e `run_game`, que é o laço da câmera.
- O `gesture_game.py` foi refatorado para usar essa base. As 9 telas de um
  roteiro fixo ficaram idênticas pixel a pixel antes e depois.
- Testes com pytest para tudo: gestos, jogo de gestos, música e synth (FFT e
  estalos), teremim, círculo, base de jogo e "Corte no Ar".

### 6. Jogo "Corte no Ar" (`corte`)
- Jogo original no estilo fruit ninja. O pedido era um "fruit ninja", mas o
  jogo não copia nome, marca nem interface (veja Originalidade no CLAUDE.md).
- **Lâmina:** o rastro do indicador (0,15s). Só corta acima de `CUT_SPEED`
  (3,5 palmas/s); mão parada não corta.
- **Colisão:** segmento do movimento no frame × círculo da fruta.
- **Frutas:** 5 tipos lançados com gravidade (a ameixa vale 2). Ao cortar,
  viram duas metades na perpendicular do corte, mais respingos e "+N".
- **Combo:** 3 ou mais frutas em até 0,3s entre cortes dão bônus igual ao
  número de frutas.
- **Vidas:** fruta perdida ou bomba cortada tira uma vida (`--bomba-fatal` =
  fim de jogo). As ondas crescem e as bombas aumentam com o tempo.
- **2 jogadores:** tela dividida, cada um corta só do seu lado, com placar e
  vidas próprios. Vence quem fizer mais pontos.
- **Som:** efeitos curtos com o `PolySynth`. Sem placa de som, o jogo segue
  mudo; `--sem-som` desliga.

## Pendências e riscos

- [ ] **Testar com câmera e som reais.** Até agora tudo foi testado com dados
      sintéticos. Limites que talvez precisem de calibração:
  - polegar em `gestures.fingers_extended` (fatores 1.1 e 0.5);
  - pinça (`PINCH_ON` e `PINCH_OFF`);
  - faixas úteis da tela no teremim (`TOP`/`BOTTOM` e `VOL_TOP`/`VOL_BOTTOM`);
  - latência do áudio no Windows (`BLOCK_SIZE`, `latency="low"`);
  - velocidade mínima de corte (`CUT_SPEED` em `slice_game.py`) e a
    dificuldade (`_difficulty`).
- [x] ~~Mergear na `master`~~: feito (#1 e #4).
- [x] ~~Converter o `.gitignore` para UTF-8~~: feito.
- [ ] Apagar as branches antigas (`claude/manual-tracking-game-3j9ia1`,
      `claude/teremim`, `claude/circulo-cromatico`) e ativar "Automatically
      delete head branches" no GitHub.
- [x] ~~Criar `tests/` com os testes sem câmera~~: feito (34 testes, pytest).
- [ ] Rever o `requirements.txt`: está em UTF-16, tem dependências sobrando e
      fixar a versão do `mediapipe` é obrigatório por causa da API
      `solutions`.
- [ ] Opcional: um `--debug` comum a todos os apps (FPS, landmarks, valores
      brutos) para ajudar na calibração.

## Próximo

A definir. Candidatos nas Ideias futuras: tocar alvos (sprites) e jogo de
ritmo, que aproveitam a base de jogo e a colisão do "Corte no Ar".

## Ideias futuras

- **Tocar alvos (sprites):** alvos aparecem em pontos da tela e precisam ser
  tocados no lugar. Aproveita a base de jogo, a pinça do círculo e a
  colisão do "Corte no Ar".
- **Teremim com 2 vozes:** usar o `PolySynth` com uma mão para cada voz.
- **Gravar e tocar de volta (looper)** no círculo cromático e no teremim.
- **Jogo de ritmo:** notas caem até o círculo cromático e é preciso tocá-las
  na hora certa.
- **Modo 2 jogadores no "Imite o Gesto":** quem fizer o gesto primeiro ganha
  o ponto.
- **Placar persistente:** recordes salvos num arquivo JSON local.
