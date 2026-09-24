# Teste comunicacao Raspberry Pi 3B <-> Arduino via Cabo USB
# Rode: python3 teste_pi.py
import serial
import time
import glob

BAUD = 115200

# auto-detecta porta do Arduino
def achar_porta():
    for p in glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"):
        return p
    return "/dev/ttyACM0"

PORTA = achar_porta()
print(f"Conectando em {PORTA} ...")

ser = serial.Serial(PORTA, BAUD, timeout=1)
time.sleep(2)  # Arduino reseta ao abrir serial
ser.reset_input_buffer()

comandos_teste = ["PING", "LED_ON", "ECO:Ola Arduino", "LED_OFF", "PING"]

try:
    for cmd in comandos_teste:
        print(f"\n[PI -> ARDUINO] {cmd}")
        ser.write((cmd + "\n").encode())
        time.sleep(0.2)

        # lê todas as respostas por 1.5s (inclui heartbeat)
        inicio = time.time()
        while time.time() - inicio < 1.5:
            if ser.in_waiting:
                resp = ser.readline().decode(errors='ignore').strip()
                if resp:
                    print(f"[ARDUINO -> PI] {resp}")

    # modo interativo
    print("\n--- Modo interativo (digite PING, LED_ON, LED_OFF, ECO:texto ou sair) ---")
    while True:
        msg = input("> ").strip()
        if msg.lower() in ("sair", "exit", "quit"):
            break
        if not msg:
            continue
        ser.write((msg + "\n").encode())
        time.sleep(0.3)
        while ser.in_waiting:
            print("Resposta:", ser.readline().decode(errors='ignore').strip())

except KeyboardInterrupt:
    print("\nEncerrado pelo usuario")
finally:
    ser.close()
