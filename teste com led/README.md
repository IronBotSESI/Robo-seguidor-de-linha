# IronBot — Robô Seguidor de Linha

Projeto de robô seguidor de linha com **visão computacional (OpenCV)** no Raspberry Pi + **Arduino Mega** para atuação/feedback via LED RGB. A comunicação entre as duas placas é feita via **USB / Serial (115200 baud)**.

Pasta: `robo/`

| Arquivo | Linguagem | Função |
|---------|-----------|--------|
| `testlinha.py` | Python | Visão computacional, lógica de decisão e envio de comandos por serial |
| `testled.ino` | C++ (Arduino) | Recepção de comandos seriais e acionamento de LED RGB + LED onboard |

---

## 1. Arquitetura

```
[Câmera USB] -> [Raspberry Pi: testlinha.py (OpenCV)] -- Serial USB 115200 --> [Arduino Mega: testled.ino] -> [LED RGB + LED onboard]
                         |                                                              |
                         +---> Janela "Robo Seguidor de Linha"                          +---> Heartbeat "ARDUINO VIVO"
                         +---> Overlay: sensores, ação, status                          +---> Respostas "OK RED", "PONG", etc.
```

O Python é o **mestre da decisão** — processa o frame, decide a ação (`PARAR`, `CURVA 90°`, `AJUSTAR`, etc.) e envia apenas a **cor** correspondente para o Arduino. O Arduino é o **atuador visual** — acende o LED RGB de acordo com a cor recebida.

Mapeamento de cor/decisão → comando serial:

| `cor_msg` (BGR no Python) | Significado | Comando Serial | Cor no LED RGB |
|---------------------------|-------------|----------------|----------------|
| `(0, 0, 255)` Vermelho | Parar / Perigo / Retorno | `RED` | Vermelho |
| `(0, 255, 0)` Verde | Seguir em frente / Centralizado | `GREEN` | Verde |
| `(0, 255, 255)` Amarelo | Curva / Ajuste / Verde lateral | `YELLOW` | Amarelo |
| `(255, 0, 0)` Azul | Linha perdida | `BLUE` | Azul |

---

## 2. Hardware Necessário

### 2.1 Lista de materiais
- Raspberry Pi (3/4/5) com Raspberry Pi OS
- Arduino Mega (ou Uno/Leonardo compatível)
- Cabo USB A-B para Arduino Mega
- Câmera USB (ou PiCamera com adaptação para `cv2.VideoCapture`)
- LED RGB cátodo comum (pino longo = GND) + 3x resistores 220Ω
- Protoboard e jumpers

### 2.2 Ligação do LED RGB — `testled.ino:12-15`

```
Pino R do LED ---> resistor 220Ω ---> pino 2 do Arduino (PIN_R)
Pino G do LED ---> resistor 220Ω ---> pino 3 do Arduino (PIN_G)
Pino B do LED ---> resistor 220Ω ---> pino 4 do Arduino (PIN_B)
GND do LED    ---> GND do Arduino
LED onboard   ---> pino 13 (LED_PIN) - já existente na placa
```

> **Anodo comum?** Se seu LED for anodo comum (pino comum no 5V), altere em `testled.ino:17`:
> ```cpp
> #define COMUM_ANODO true
> ```
> Isso inverte a lógica PWM em `aplicaCor()` — `testled.ino:21-28`.

> **Nota:** O comentário no cabeçalho do `.ino` (`testled.ino:5-7`) menciona pinos 9/10/11 como exemplo, mas o código efetivo usa **2/3/4**. Siga os pinos do `#define`.

---

## 3. `testled.ino` — Firmware do Arduino

### 3.1 O que faz
1.  Inicializa serial a **115200 baud** e aguarda conexão (`testled.ino:76-78`).
2.  Escuta comandos por `Serial.readStringUntil('\n')` em `loop()` (`testled.ino:83-86`).
3.  Aciona o LED RGB via `analogWrite` em `aplicaCor()` e `mostraCor()` (`testled.ino:21-67`).
4.  Envia heartbeat a cada 2s: `ARDUINO VIVO em Xs` (`testled.ino:119-124`).
5.  Responde com `OK <COR>`, `PONG`, `ECO_RETORNO:` ou `RECEBIDO_DESCONHECIDO:`.

### 3.2 Protocolo Serial

| Comando enviado (Python → Arduino) | Resposta (Arduino → Python) | Ação |
|------------------------------------|-----------------------------|------|
| `PING` | `PONG` | Teste de conexão |
| `LED_ON` / `LED_OFF` | `OK LED ON` / `OK LED OFF` | Liga/desliga LED onboard (pino 13) |
| `RED` / `R` | `OK RED` | LED RGB vermelho |
| `GREEN` / `G` | `OK GREEN` | LED RGB verde |
| `BLUE` / `B` | `OK BLUE` | LED RGB azul |
| `YELLOW` / `Y` | `OK YELLOW` | LED RGB amarelo |
| `WHITE` / `W` | `OK WHITE` | LED RGB branco |
| `CYAN` / `C` | `OK CYAN` | LED RGB ciano |
| `MAGENTA` / `M` | `OK MAGENTA` | LED RGB magenta |
| `OFF` / `O` / `BLACK` / `K` | `OK OFF` | Apaga LED RGB |
| `ECO:<texto>` | `ECO_RETORNO:<texto>` | Echo para debug |
| *(qualquer outro)* | `RECEBIDO_DESCONHECIDO:<cmd>` | Erro / log |
| *(heartbeat automático)* | `ARDUINO VIVO em Xs` | Prova de vida a cada 2s |

Todos os comandos são **case-insensitive** (`cmd.toUpperCase()` em `testled.ino:86`) e terminados com `\n`.

### 3.3 Como carregar

1.  Abra `testled.ino` na Arduino IDE.
2.  Selecione **Placa: Arduino Mega** e a porta COM correta.
3.  Clique em **Upload**.
4.  Abra o Monitor Serial (115200 baud) e verifique `ARDUINO PRONTO` + heartbeat.

---

## 4. `testlinha.py` — Visão Computacional (Raspberry Pi / PC)

### 4.1 Dependências

```bash
py -m pip install opencv-python numpy pyserial
# no Raspberry Pi:
pip3 install opencv-python numpy pyserial
```

| Biblioteca | Uso no código |
|------------|---------------|
| `cv2` (OpenCV) | Captura de vídeo, conversão HSV, máscaras, contornos, overlay |
| `numpy` | Faixas de cor HSV (`VERDE_LOW/HIGH`, `RED1/RED2`, etc.) |
| `pyserial` | Comunicação com Arduino (`conectar_arduino()`, `enviar_cor()`) |
| `glob` + `serial.tools.list_ports` | Auto-detecção de portas (`/dev/ttyACM*`, `/dev/ttyUSB*`, `COMx`) |

### 4.2 Fluxo de execução

```
1. conectar_arduino()                    # testlinha.py:21-60
   -> varre list_ports + /dev/ttyACM* / USB*
   -> tenta abrir a 115200, sleep 2s (reset do Arduino)
   -> retorna objeto serial ou None (modo offline)

2. loop principal (while True)           # testlinha.py:96-250
   a) Captura frame + flip horizontal    # :101
   b) Define 2 ROIs:
      - ROI verificação: 40%–55% da altura (linha à frente)
      - ROI sensores:    65%–85% da altura (5 sensores virtuais)
   c) Converte para HSV e cria 4 máscaras:
      - mask_verde (verde 35-85 HSV)     # :117
      - mask_vermelho (0-10 + 160-180)   # :119-121 (vermelho precisa 2 faixas)
      - mask_linha_sens (V < 70)         # :123 (linha preta)
      - mask_linha_verif (V < 70)        # :124
   d) Verifica linha à frente            # :127  (>300 px pretos na ROI superior)
   e) Detecta marcações verdes           # :130-142 (contornos >150px, separa esq/dir por centro_x)
   f) Lê 5 sensores virtuais             # :144-159 (divide ROI em 5 faixas verticais, >200 px = linha)
   g) Lógica de decisão (5 prioridades)  # :176-231
   h) Envia cor para Arduino se mudou    # :238-245 (evita flood serial)
   i) Mostra janela + 'q' para sair      # :247-250
```

### 4.3 As 5 Prioridades da Lógica de Decisão — `testlinha.py:173-231`

A ordem é **rigorosa** — `if/elif` garante que vermelho sempre vence, etc.

| Prioridade | Condição | Ação | `cor_msg` | LED |
|------------|----------|------|-----------|-----|
| **1 — Vermelho** | `countNonZero(mask_vermelho) > 400` (`testlinha.py:167`) | `PARAR (VERMELHO)` | `(0,0,255)` | `RED` |
| **2 — Verde** | `verde_esq && verde_dir` | `RETORNO 180° (VERDE DUPLO)` | `(0,0,255)` | `RED` |
| | `verde_esq` apenas | `VERDE ESQUERDA` | `(0,255,255)` | `YELLOW` |
| | `verde_dir` apenas | `VERDE DIREITA` | `(0,255,255)` | `YELLOW` |
| **3 — Interseção** | `linha_na_frente && (total_ativos >=3 ou padrão 90°)` | `INTERSEÇÃO — SEGUIR EM FRENTE` | `(0,255,0)` | `GREEN` |
| **4 — Curva 90°** | `!linha_na_frente && (total_ativos >=3 ou padrão 90°)` | `CURVA 90° ESQ/DIR (3 ou 4 sensores)` ou `PARAR / T (5 sensores)` | `(0,255,255)` / `(0,0,255)` | `YELLOW` / `RED` |
| **5 — Segue linha** | casos restantes | `CENTRALIZADO` / `AJUSTAR ESQ/DIR` / `LINHA PERDIDA` | `(0,255,0)` / `(0,255,255)` / `(255,0,0)` | `GREEN` / `YELLOW` / `BLUE` |

Detalhes de padrão 90° (`testlinha.py:169-170`):
```python
padrao_90_esq = (sensores[0]==1 and sensores[1]==1 and sensores[2]==1)  # S1+S2+S3
padrao_90_dir = (sensores[2]==1 and sensores[3]==1 and sensores[4]==1)  # S3+S4+S5
```

### 4.4 Sensores Virtuais

- `NUM_SENSORES = 5` (`testlinha.py:94`) — divide a largura do frame em 5 colunas iguais.
- Cada sensor = 1 se `countNonZero(sub_linha) > 200` (`testlinha.py:154`).
- Overlay na tela: retângulo **verde** = linha detectada, **cinza** = sem linha (`testlinha.py:157-159`).

### 4.5 Calibração — `testlinha.py:86-94`

```python
VERDE_LOW  = [35, 35, 35]   # HSV mínimo para verde
VERDE_HIGH = [85, 255, 255] # HSV máximo para verde
RED1_LOW/HIGH = [0, 100, 70]   -> [10, 255, 255]   # vermelho faixa 1
RED2_LOW/HIGH = [160, 100, 70] -> [180, 255, 255]  # vermelho faixa 2 (wrap-around do Hue)
LIMITE_BRILHO_LINHA = 70    # V < 70 = preto (linha)
```

**Como calibrar:**
- Use um script auxiliar com `cv2.createTrackbar` para ajustar HSV em tempo real.
- Iluminação muda tudo — calibre no local da pista.
- Linha preta: ajuste `LIMITE_BRILHO_LINHA` (aumente se a linha não é detectada, diminua se o chão vira falso positivo).
- Verde/vermelho: ajuste `S` e `V` mínimos (segundo e terceiro valores) para filtrar sombras.

### 4.6 Comunicação Serial — `testlinha.py:21-79`

- `conectar_arduino()` testa todas as portas encontradas e faz `sleep(2)` para o auto-reset do Arduino.
- `enviar_cor()` é **não-bloqueante**: escreve `cmd + "\n"` e esvazia `in_waiting` com `readline()` sem travar a visão.
- Só envia se `cmd_cor != ultimo_cmd_enviado` (`testlinha.py:243`) — reduz tráfego.
- Se `pyserial` não estiver instalado ou nenhuma porta for encontrada, o código segue em **modo offline** (só visão, sem LED).
- Ao sair (`q`), envia `OFF` e fecha a porta (`testlinha.py:252-255`).

### 4.7 Como executar

```bash
# 1. Instale dependências
py -m pip install opencv-python numpy pyserial

# 2. Conecte Arduino via USB e câmera

# 3. Rode
python testlinha.py
# ou
py testlinha.py

# 4. Janela "Robo Seguidor de Linha" abrirá:
#    - Retângulos S1..S5 (sensores)
#    - Retângulo "LINHA A FRENTE" (verde/vermelho)
#    - Texto: Sensores, Ação, Arduino status
#    - Pressione 'q' para sair (apaga LED)
```

> No Raspberry Pi, se a câmera for PiCamera, troque `cv2.VideoCapture(0)` por `cv2.VideoCapture(0, cv2.CAP_V4L2)` ou use `picamera2`.

---

## 5. Protocolo Integrado

Exemplo de sessão:

```
[Python] -> "GREEN\n"  (centralizado)
[Arduino] <- "OK GREEN" (acende verde) + "ARDUINO VIVO em 4s" (a cada 2s)
[Python] -> "YELLOW\n" (ajustar esquerda)
[Arduino] <- "OK YELLOW"
[Python] -> "RED\n"    (vermelho detectado)
[Arduino] <- "OK RED"
```

Teste manual pelo Monitor Serial / terminal:

```bash
# Linux/Raspberry
echo "RED" > /dev/ttyACM0
echo "PING" > /dev/ttyACM0  # espera PONG
```

---

## 6. Troubleshooting

| Problema | Causa provável | Solução |
|----------|----------------|---------|
| `Arduino: OFFLINE` | Porta não encontrada / permissão | `sudo usermod -a -G dialout $USER` + relogar; verifique `dmesg \| grep tty` |
| LED RGB não acende | Pinos errados / cátodo vs anodo | Confira `PIN_R/G/B = 2/3/4` e `COMUM_ANODO`; teste com `LED_ON` |
| LED com cor errada | Fiação R/G/B trocada | Troque jumpers ou ajuste `#define PIN_R/G/B` |
| Linha não detectada | `LIMITE_BRILHO_LINHA` baixo / iluminação | Aumente para 80–90; verifique máscara com `cv2.imshow("mask", mask_linha_sens)` |
| Verde não detectado | Faixa HSV descalibrada | Recalibre `VERDE_LOW/HIGH` no local |
| Vermelho com falso positivo | Faixa muito larga | Aumente `S` mínimo de 100 para 120 |
| Janela trava / lag | `in_waiting` bloqueando | Já tratado com `timeout=0.05`; reduza resolução: `cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)` |
| `pyserial not installed` | Falta instalar | `py -m pip install pyserial` |

---

## 7. Próximos Passos / Extensões

- [ ] Substituir LED RGB por **controle de motores** (ponte H L298N) — mapear `acao` para PWM de motores em vez de `RED/GREEN/...`.
- [ ] Adicionar **PID** no `AJUSTAR ESQUERDA/DIREITA` usando erro = posição do centro da linha.
- [ ] Salvar calibração HSV em `config.json`.
- [ ] Adicionar `argparse` para `--port`, `--baud`, `--camera`, `--no-arduino`.

---

## 8. Licença e Autoria

Projeto educacional — IronBot. Códigos de teste para validação de comunicação e visão antes da integração completa com chassi/motores.

