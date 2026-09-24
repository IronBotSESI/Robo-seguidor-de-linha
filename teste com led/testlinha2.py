# py -m pip install opencv-python numpy pyserial
import cv2
import numpy as np
import time

# --- CONFIG SERIAL / LED RGB ---
# Mapeia a cor de decisão (cor_msg em BGR, como está na Lógica de decisão)
# para o comando enviado ao Arduino:
#   (0,0,255) vermelho -> "RED"
#   (0,255,0) verde    -> "GREEN"
#   (0,255,255) amarelo-> "YELLOW"
#   (255,0,0) azul     -> "BLUE"
BAUD = 115200
COR_PARA_CMD = {
    (0, 0, 255): "RED",
    (0, 255, 0): "GREEN",
    (0, 255, 255): "YELLOW",
    (255, 0, 0): "BLUE",
}

def conectar_arduino(baud=BAUD):
    """Tenta abrir a serial com o Arduino. Retorna objeto serial ou None."""
    try:
        import serial
        from serial.tools import list_ports
    except ImportError:
        print("[AVISO] pyserial nao instalado. Rode: py -m pip install pyserial")
        print("[AVISO] Seguindo SEM Arduino (só visão).")
        return None

    candidatos = []
    # 1) Portas detectadas automaticamente (funciona no Windows COMx e no Pi /dev/tty*)
    try:
        for p in list_ports.comports():
            candidatos.append(p.device)
    except Exception:
        pass
    # 2) Fallbacks comuns no Raspberry Pi
    import glob
    candidatos += glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")
    # remove duplicadas mantendo ordem
    vistos = set()
    portas = [p for p in candidatos if not (p in vistos or vistos.add(p))]

    if not portas:
        print("[AVISO] Nenhuma porta serial encontrada. Seguindo SEM Arduino.")
        return None

    for porta in portas:
        try:
            ser = serial.Serial(porta, baud, timeout=0.05)
            time.sleep(2)  # Arduino reseta ao abrir a serial
            ser.reset_input_buffer()
            print(f"[OK] Arduino conectado em {porta}")
            return ser
        except Exception as e:
            print(f"[INFO] Falha em {porta}: {e}")
            continue
    print("[AVISO] Nao foi possivel abrir nenhuma porta. Seguindo SEM Arduino.")
    return None


def enviar_cor(ser, cmd):
    """Envia comando de cor (RED/GREEN/YELLOW/BLUE/OFF) sem travar o loop."""
    if ser is None:
        return
    try:
        ser.write((cmd + "\n").encode())
        # Leitura nao-bloqueante: esvazia respostas/heartbeat sem travar a visao
        while ser.in_waiting:
            try:
                resp = ser.readline().decode(errors="ignore").strip()
                if resp:
                    print(f"[ARDUINO] {resp}")
            except Exception:
                break
    except Exception as e:
        print(f"[AVISO] Erro ao enviar {cmd}: {e}")


arduino = conectar_arduino()
ultimo_cmd_enviado = None

cap = cv2.VideoCapture(0)

# --- FAIXAS DE CORES CALIBRADAS ---
# ANTES: VERDE_LOW = [35,35,35] -> muito permissivo, pega sombra/reflexo como verde e pisca
# AGORA: S e V minimos mais altos = só verde vivo e bem iluminado vira detecção
VERDE_LOW = np.array([35, 70, 70])
VERDE_HIGH = np.array([85, 255, 255])

RED1_LOW, RED1_HIGH = np.array([0, 100, 70]), np.array([10, 255, 255])
RED2_LOW, RED2_HIGH = np.array([160, 100, 70]), np.array([180, 255, 255])

LIMITE_BRILHO_LINHA = 70 
NUM_SENSORES = 5

# --- FILTROS ANTI-RUIDO E ANTI-PISCA (CORREÇÃO) ---
KERNEL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
VERDE_AREA_MIN = 650        # antes 150 -> muito pequeno, qualquer pixel verde virava marcador
VERDE_AREA_MAX = 12000      # ignora parede/mesa verde gigante
VERDE_LADO_MIN = 18         # largura/altura minima do marcador
SOLIDEZ_MIN = 0.45          # ignora contorno recortado/ruido (solidez = area / area_bbox)

# Debounce temporal do verde: precisa ver por N frames seguidos para validar
# e precisa sumir por M frames para desativar (histerese). Elimina o pisca.
FRAMES_CONFIRMA_VERDE = 5
FRAMES_PERDE_VERDE = 8
cont_verde_esq = 0
cont_verde_dir = 0
cont_perda_esq = 0
cont_perda_dir = 0
verde_esq_estavel = False
verde_dir_estavel = False

# Debounce do LED/comando: evita o LED piscar quando a decisao oscila 1 frame
FRAMES_CONFIRMA_CMD = 4
cont_cmd = 0
ultimo_cmd_candidato = None

# Para debug: coloque True para ver as mascaras em janelas separadas
DEBUG_MASCARAS = False

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    frame = cv2.flip(frame, 1)

    altura, largura, _ = frame.shape
    centro_x = largura // 2

    # 1. REGIÕES DE INTERESSE (ROIs)
    y_verif_1, y_verif_2 = int(altura * 0.40), int(altura * 0.55)
    roi_verif = frame[y_verif_1:y_verif_2, :]

    y_sens_1, y_sens_2 = int(altura * 0.65), int(altura * 0.85)
    roi_sens = frame[y_sens_1:y_sens_2, :]

    hsv_verif = cv2.cvtColor(roi_verif, cv2.COLOR_BGR2HSV)
    hsv_sens = cv2.cvtColor(roi_sens, cv2.COLOR_BGR2HSV)

    # 2. MÁSCARAS DE COR + FILTRO MORFOLOGICO (remove ruido pontual)
    mask_verde = cv2.inRange(hsv_sens, VERDE_LOW, VERDE_HIGH)
    # open = remove pontos brancos pequenos (ruido), close = fecha buracos dentro do marcador
    mask_verde = cv2.morphologyEx(mask_verde, cv2.MORPH_OPEN, KERNEL)
    mask_verde = cv2.morphologyEx(mask_verde, cv2.MORPH_CLOSE, KERNEL)

    m_r1 = cv2.inRange(hsv_sens, RED1_LOW, RED1_HIGH)
    m_r2 = cv2.inRange(hsv_sens, RED2_LOW, RED2_HIGH)
    mask_vermelho = cv2.bitwise_or(m_r1, m_r2)
    mask_vermelho = cv2.morphologyEx(mask_vermelho, cv2.MORPH_OPEN, KERNEL)

    mask_linha_sens = cv2.inRange(hsv_sens, np.array([0, 0, 0]), np.array([180, 255, LIMITE_BRILHO_LINHA]))
    mask_linha_verif = cv2.inRange(hsv_verif, np.array([0, 0, 0]), np.array([180, 255, LIMITE_BRILHO_LINHA]))

    # 3. VERIFICAÇÃO DE LINHA À FRENTE
    linha_na_frente = cv2.countNonZero(mask_linha_verif) > 300

    # 4. DETECÇÃO DE MARCAÇÕES VERDES (COM FILTROS ANTI-FALSO-POSITIVO)
    verde_esq_raw, verde_dir_raw = False, False
    contornos_v, _ = cv2.findContours(mask_verde, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for c in contornos_v:
        area = cv2.contourArea(c)
        if area < VERDE_AREA_MIN or area > VERDE_AREA_MAX:
            continue

        x, y, w, h = cv2.boundingRect(c)
        if w < VERDE_LADO_MIN or h < VERDE_LADO_MIN:
            continue

        aspecto = w / float(h) if h > 0 else 0
        if aspecto > 3.5 or aspecto < 0.28:  # muito alongado = faixa/ruido, nao quadrado de curva
            continue

        solidez = area / (w * h) if (w * h) > 0 else 0
        if solidez < SOLIDEZ_MIN:  # contorno muito recortado/esburacado = reflexo/sombra
            continue

        # Opcional: ignora verde muito longe da linha preta (marcador falso no fundo)
        # Verifica se há linha preta perto do marcador (dentro do bbox expandido)
        # Se não houver linha por perto, provavelmente é objeto verde aleatório no ambiente
        pad = 10
        x1b = max(0, x - pad)
        y1b = max(0, y - pad)
        x2b = min(mask_linha_sens.shape[1], x + w + pad)
        y2b = min(mask_linha_sens.shape[0], y + h + pad)
        roi_linha_perto = mask_linha_sens[y1b:y2b, x1b:x2b]
        if cv2.countNonZero(roi_linha_perto) < 40:  # sem linha perto = ignora
            continue

        M = cv2.moments(c)
        if M["m00"] > 0:
            cx = int(M["m10"] / M["m00"])
            # cx é relativo ao roi_sens, que tem mesma largura do frame
            if cx < centro_x:
                verde_esq_raw = True
            else:
                verde_dir_raw = True
            cv2.drawContours(roi_sens, [c], -1, (0, 255, 0), 2)
            # desenha bbox para debug
            cv2.rectangle(roi_sens, (x, y), (x + w, y + h), (0, 255, 255), 1)

    # --- DEBOUNCE / HISTERESE DO VERDE (ANTI-PISCA) ---
    # Para ATIVAR: precisa detectar verde por FRAMES_CONFIRMA_VERDE frames seguidos
    # Para DESATIVAR: precisa ficar sem ver verde por FRAMES_PERDE_VERDE frames seguidos
    # Isso filtra aquele pisca de 1 frame que vinha de reflexo/luz

    # Esquerda
    if verde_esq_raw:
        cont_verde_esq += 1
        cont_perda_esq = 0
        if cont_verde_esq >= FRAMES_CONFIRMA_VERDE:
            verde_esq_estavel = True
    else:
        if verde_esq_estavel:
            cont_perda_esq += 1
            if cont_perda_esq >= FRAMES_PERDE_VERDE:
                verde_esq_estavel = False
                cont_verde_esq = 0
                cont_perda_esq = 0
        else:
            cont_verde_esq = max(0, cont_verde_esq - 1)

    # Direita
    if verde_dir_raw:
        cont_verde_dir += 1
        cont_perda_dir = 0
        if cont_verde_dir >= FRAMES_CONFIRMA_VERDE:
            verde_dir_estavel = True
    else:
        if verde_dir_estavel:
            cont_perda_dir += 1
            if cont_perda_dir >= FRAMES_PERDE_VERDE:
                verde_dir_estavel = False
                cont_verde_dir = 0
                cont_perda_dir = 0
        else:
            cont_verde_dir = max(0, cont_verde_dir - 1)

    verde_esq = verde_esq_estavel
    verde_dir = verde_dir_estavel

    # 5. LEITURA DOS 5 SENSORES
    largura_sens = largura // NUM_SENSORES
    sensores = [0] * NUM_SENSORES

    for i in range(NUM_SENSORES):
        x1 = i * largura_sens
        x2 = (i + 1) * largura_sens if i < NUM_SENSORES - 1 else largura

        sub_linha = mask_linha_sens[:, x1:x2]

        if cv2.countNonZero(sub_linha) > 200:
            sensores[i] = 1

        cor_box = (0, 255, 0) if sensores[i] == 1 else (100, 100, 100)
        cv2.rectangle(frame, (x1, y_sens_1), (x2, y_sens_2), cor_box, 2)
        cv2.putText(frame, f"S{i+1}", (x1 + 10, y_sens_1 + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, cor_box, 1)

    cor_verif = (0, 255, 0) if linha_na_frente else (0, 0, 255)
    cv2.rectangle(frame, (0, y_verif_1), (largura, y_verif_2), cor_verif, 2)
    cv2.putText(frame, "LINHA A FRENTE" if linha_na_frente else "SEM LINHA A FRENTE", 
                (10, y_verif_1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, cor_verif, 2)

    # --- VARIÁVEIS DE AUXÍLIO PARA A LÓGICA ---
    vermelho_detectado = cv2.countNonZero(mask_vermelho) > 700  # antes 400 -> muito sensivel
    total_ativos = sum(sensores)
    padrao_90_esq = (sensores[0] == 1 and sensores[1] == 1 and sensores[2] == 1)
    padrao_90_dir = (sensores[2] == 1 and sensores[3] == 1 and sensores[4] == 1)

    # =========================================================================
    # LÓGICA DE DECISÃO (ORDEM RIGOROSA DE PRIORIDADE)
    # =========================================================================

    # 1. PRIORIDADE 1: VERMELHO
    if vermelho_detectado:
        acao = "PARAR (VERMELHO)"
        cor_msg = (0, 0, 255)

    # 2. PRIORIDADE 2: VERDE (agora com debounce, nao pisca mais)
    elif verde_esq and verde_dir:
        acao = "RETORNO 180° (VERDE DUPLO)"
        cor_msg = (0, 0, 255)
    elif verde_esq:
        acao = f"VERDE ESQUERDA | Frente: {'SIM' if linha_na_frente else 'NAO'}"
        cor_msg = (0, 255, 255)
    elif verde_dir:
        acao = f"VERDE DIREITA | Frente: {'SIM' if linha_na_frente else 'NAO'}"
        cor_msg = (0, 255, 255)

    # 3. PRIORIDADE 3: INTERSEÇÕES (Possui linha à frente)
    elif linha_na_frente and (total_ativos >= 3 or padrao_90_esq or padrao_90_dir):
        acao = "INTERSEÇÃO DETECTADA - SEGUIR EM FRENTE"
        cor_msg = (0, 255, 0)

    # 4. PRIORIDADE 4: CURVAS DE 90 GRAUS (Não possui linha à frente)
    elif not linha_na_frente and (total_ativos >= 3 or padrao_90_esq or padrao_90_dir):
        if total_ativos == 4:
            soma_esq = sensores[0] + sensores[1]
            soma_dir = sensores[3] + sensores[4]
            if soma_esq > soma_dir:
                acao = "CURVA 90° ESQUERDA (4 SENSORES)"
                cor_msg = (0, 255, 255)
            else:
                acao = "CURVA 90° DIREITA (4 SENSORES)"
                cor_msg = (0, 255, 255)
        elif total_ativos == 5:
            acao = "PARAR / CRUZAMENTO EM T (5 SENSORES SEM LINHA FRENTE)"
            cor_msg = (0, 0, 255)
        elif padrao_90_esq:
            acao = "CURVA 90° ESQUERDA (3 SENSORES)"
            cor_msg = (0, 255, 255)
        elif padrao_90_dir:
            acao = "CURVA 90° DIREITA (3 SENSORES)"
            cor_msg = (0, 255, 255)

    # 5. PRIORIDADE 5: SEGUE LINHA CONVENCIONAL
    else:
        if sensores == [0, 0, 1, 0, 0] or sensores == [0, 1, 1, 1, 0]:
            acao = "CENTRALIZADO"
            cor_msg = (0, 255, 0)
        elif sensores[0] == 1 or sensores[1] == 1:
            acao = "AJUSTAR ESQUERDA"
            cor_msg = (0, 255, 255)
        elif sensores[3] == 1 or sensores[4] == 1:
            acao = "AJUSTAR DIREITA"
            cor_msg = (0, 255, 255)
        else:
            acao = "LINHA PERDIDA"
            cor_msg = (255, 0, 0)

    # Exibição de Informações na Tela
    cv2.putText(frame, f"Sensores: {sensores}", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(frame, f"Acao: {acao}", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_msg, 2)
    # debug do debounce
    dbg_verde = f"Verde RAW: E{int(verde_esq_raw)} D{int(verde_dir_raw)} | ESTAVEL: E{int(verde_esq)} D{int(verde_dir)}"
    cv2.putText(frame, dbg_verde, (20, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

    # --- ENVIA COR PARA O ARDUINO ACENDER O LED RGB (COM DEBOUNCE DO COMANDO) ---
    cmd_cor = COR_PARA_CMD.get(tuple(cor_msg), "OFF")
    status_ser = f"Arduino: {cmd_cor}" if arduino else "Arduino: OFFLINE"
    cv2.putText(frame, status_ser, (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    # Anti-pisca do LED: só troca de cor se a mesma decisão se repetir por N frames
    # Vermelho é emergencia e passa na hora
    if cmd_cor == "RED":
        # vermelho sempre envia imediatamente
        if cmd_cor != ultimo_cmd_enviado:
            enviar_cor(arduino, cmd_cor)
            ultimo_cmd_enviado = cmd_cor
        ultimo_cmd_candidato = cmd_cor
        cont_cmd = FRAMES_CONFIRMA_CMD
    else:
        if cmd_cor == ultimo_cmd_candidato:
            cont_cmd += 1
        else:
            ultimo_cmd_candidato = cmd_cor
            cont_cmd = 1
        
        if cont_cmd >= FRAMES_CONFIRMA_CMD:
            if cmd_cor != ultimo_cmd_enviado:
                enviar_cor(arduino, cmd_cor)
                ultimo_cmd_enviado = cmd_cor

    cv2.imshow("Robo Seguidor de Linha", frame)
    if DEBUG_MASCARAS:
        cv2.imshow("mask_verde (filtrada)", mask_verde)
        cv2.imshow("mask_vermelho", mask_vermelho)
        cv2.imshow("mask_linha", mask_linha_sens)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

if arduino:
    try:
        arduino.write(b"OFF\n")  # apaga o LED ao sair
        arduino.close()
    except Exception:
        pass
cap.release()
cv2.destroyAllWindows()
