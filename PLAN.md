# PLAN.md

Roteiro das funcionalidades de hand tracking: o que foi feito, o que vem a
seguir e as pendências. Detalhes técnicos estão no CLAUDE.md.

## Visão

Uma coleção de experiências controladas pelas mãos via webcam. Cada uma é um
script separado e roda com `python main.py <comando>`. Todas compartilham o
tracking, o reconhecimento de gestos, o desenho e o áudio em `apps/common/`.

## Feito

| # | Funcionalidade | Comando | Branch | Status |
|---|---|---|---|---|
| 0 | Controle do mouse (original) | `mouse` | `master` | ok |
| 1 | Lançador + módulos comuns | `python main.py` | `claude/manual-tracking-game-3j9ia1` | ok |
| 2 | Jogo "Imite o Gesto" | `gestos` | `claude/manual-tracking-game-3j9ia1` | testado sem câmera |
| 3 | Simulador de teremim | `teremim` | `claude/teremim` | testado sem câmera |
| 4 | Círculo cromático musical | `circulo` | `claude/circulo-cromatico` | testado sem câmera |

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

## Pendências e riscos

- [ ] **Testar com câmera e som reais.** Até agora tudo foi testado com dados
      sintéticos. Limites que talvez precisem de calibração:
  - polegar em `gestures.fingers_extended` (fatores 1.1 e 0.5);
  - pinça (`PINCH_ON` e `PINCH_OFF`);
  - faixas úteis da tela no teremim (`TOP`/`BOTTOM` e `VOL_TOP`/`VOL_BOTTOM`);
  - latência do áudio no Windows (`BLOCK_SIZE`, `latency="low"`).
- [ ] **Mergear na `master`.** O merge de `claude/circulo-cromatico` traz tudo
      e resolve a correção do texto que falta na branch do jogo.
- [ ] Converter o `.gitignore` da `master` para UTF-8. Já foi feito nas
      branches e é resolvido pelo merge.
- [ ] Criar `tests/` com os testes sem câmera (gestos sintéticos, synth via
      FFT, mãos falsas, renderização). Hoje eles rodaram só durante o
      desenvolvimento e não estão no repositório.
- [ ] Rever o `requirements.txt`: está em UTF-16, tem dependências sobrando e
      fixar a versão do `mediapipe` é obrigatório por causa da API
      `solutions`.
- [ ] Opcional: um `--debug` comum a todos os apps (FPS, landmarks, valores
      brutos) para ajudar na calibração.

## Próximo: Fruit Ninja (`ninja`)

Branch sugerida: `claude/fruit-ninja`, a partir de `claude/circulo-cromatico`
ou da `master` depois do merge.

### Passo 0: base de jogo comum (refatoração)
- Extrair do `gesture_game.py` um `apps/common/game.py` com:
  - estados (início, jogando, fim de jogo);
  - pontos, vidas e recorde;
  - HUD (pontos e corações);
  - telas de início e fim de jogo;
  - laço principal: câmera, espelho, tracker, update, draw e teclas.
- Refatorar o jogo de gestos para usar essa base. O comportamento não pode
  mudar.

### Jogabilidade
- **Lâmina:** o indicador corta. Guardar o rastro dos últimos ~8 frames de
  `(x, y, t)` e desenhar um traço que vai sumindo.
- **Corte válido:** só quando a velocidade do dedo passa de um limite, medido
  em palmas por segundo para não depender da distância à câmera. Mão parada
  não corta.
- **Colisão:** o segmento entre o frame anterior e o atual do rastro
  intersecta o círculo da fruta.
- **Frutas:** lançadas de baixo com velocidade inicial e gravidade, desenhadas
  com formas do OpenCV (círculos coloridos com detalhes). Ao cortar, viram
  duas metades caindo na direção do corte, mais respingos.
- **Bomba:** cortar tira uma vida, ou encerra o jogo, a definir.
- **Fruta perdida:** se cair sem ser cortada, tira uma vida. São 3 vidas.
- **Pontos:** 1 por fruta, com bônus de combo para 3 ou mais frutas no mesmo
  golpe (~0,3s).
- **Dificuldade:** mais frutas por onda e mais bombas com o tempo.
- **Som (opcional):** efeito de corte com o `synth`, por exemplo um ruído
  curto filtrado ou uma nota que sobe com o combo.

### 2 jogadores
- Duas lâminas, uma por mão, com id por lado da tela ou pelo `label`.
- Modo `--jogadores 2`: tela dividida, cada jogador corta só as frutas do seu
  lado e tem placar separado.

### Testes sem câmera
- Física com passo de tempo fixo (trajetória, tempo de queda).
- Colisão segmento × círculo (casos que atravessam, que tangenciam e que
  ficam fora).
- Rastro rápido contra rastro lento (limite de velocidade).
- Renderizar telas com frutas, metades e fim de jogo.

## Ideias futuras

- **Tocar alvos (sprites):** alvos aparecem em pontos da tela e precisam ser
  tocados no lugar. Aproveita a base de jogo, a pinça do círculo e a
  colisão do ninja.
- **Teremim com 2 vozes:** usar o `PolySynth` com uma mão para cada voz.
- **Gravar e tocar de volta (looper)** no círculo cromático e no teremim.
- **Jogo de ritmo:** notas caem até o círculo cromático e é preciso tocá-las
  na hora certa.
- **Modo 2 jogadores no "Imite o Gesto":** quem fizer o gesto primeiro ganha
  o ponto.
- **Placar persistente:** recordes salvos num arquivo JSON local.
