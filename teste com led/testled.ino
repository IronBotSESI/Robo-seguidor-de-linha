// Teste comunicacao Arduino Mega <-> Raspberry Pi via Cabo USB / Serial
// + LED RGB indicando a cor da decisao enviada pelo Python (testeSegueLinha_copy.py)
//
// Ligacao sugerida (catodo comum, o pino mais longo no GND):
//   Pino R do LED -> resistor 220R -> pino 9 (PWM)
//   Pino G do LED -> resistor 220R -> pino 10 (PWM)
//   Pino B do LED -> resistor 220R -> pino 11 (PWM)
//   GND do LED    -> GND do Arduino
// Se o seu LED for ANODO comum: ligue o pino comum no 5V e mude
// COMUM_ANODO para true abaixo.

#define LED_PIN 13      // LED onboard (mantido p/ compatibilidade)
#define PIN_R 2         // PWM
#define PIN_G 3        // PWM
#define PIN_B 4        // PWM

#define COMUM_ANODO false  // true = anodo comum (logica invertida)

unsigned long ultimoHeartbeat = 0;

void aplicaCor(int r, int g, int b) {
#if COMUM_ANODO
  r = 255 - r; g = 255 - g; b = 255 - b;
#endif
  analogWrite(PIN_R, r);
  analogWrite(PIN_G, g);
  analogWrite(PIN_B, b);
}

void mostraCor(const String &cmd) {
  if (cmd == "RED" || cmd == "R") {
    aplicaCor(255, 0, 0);
    Serial.println("OK RED");
  }
  else if (cmd == "GREEN" || cmd == "G") {
    aplicaCor(0, 255, 0);
    Serial.println("OK GREEN");
  }
  else if (cmd == "BLUE" || cmd == "B") {
    aplicaCor(0, 0, 255);
    Serial.println("OK BLUE");
  }
  else if (cmd == "YELLOW" || cmd == "Y") {
    aplicaCor(255, 255, 0);
    Serial.println("OK YELLOW");
  }
  else if (cmd == "WHITE" || cmd == "W") {
    aplicaCor(255, 255, 255);
    Serial.println("OK WHITE");
  }
  else if (cmd == "CYAN" || cmd == "C") {
    aplicaCor(0, 255, 255);
    Serial.println("OK CYAN");
  }
  else if (cmd == "MAGENTA" || cmd == "M") {
    aplicaCor(255, 0, 255);
    Serial.println("OK MAGENTA");
  }
  else if (cmd == "OFF" || cmd == "O" || cmd == "BLACK" || cmd == "K") {
    aplicaCor(0, 0, 0);
    Serial.println("OK OFF");
  }
  else {
    Serial.print("RECEBIDO_DESCONHECIDO:");
    Serial.println(cmd);
  }
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  pinMode(PIN_R, OUTPUT);
  pinMode(PIN_G, OUTPUT);
  pinMode(PIN_B, OUTPUT);
  aplicaCor(0, 0, 0); // comeca apagado
  Serial.begin(115200);
  while (!Serial) { ; } // espera no Leonardo/Micro
  Serial.println("ARDUINO PRONTO");
}

void loop() {
  // 1. Recebe comandos do Raspberry
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    cmd.toUpperCase();

    if (cmd == "PING") {
      Serial.println("PONG");
    }
    else if (cmd == "LED_ON") {
      digitalWrite(LED_PIN, HIGH);
      Serial.println("OK LED ON");
    }
    else if (cmd == "LED_OFF") {
      digitalWrite(LED_PIN, LOW);
      Serial.println("OK LED OFF");
    }
    // --- Cores do LED RGB (enviadas pelo testeSegueLinha_copy.py) ---
    else if (cmd == "RED" || cmd == "GREEN" || cmd == "BLUE" ||
             cmd == "YELLOW" || cmd == "WHITE" || cmd == "CYAN" ||
             cmd == "MAGENTA" || cmd == "OFF" || cmd == "BLACK" ||
             cmd == "R" || cmd == "G" || cmd == "B" || cmd == "Y" ||
             cmd == "W" || cmd == "C" || cmd == "M" || cmd == "O" ||
             cmd == "K") {
      mostraCor(cmd);
    }
    else if (cmd.startsWith("ECO:")) {
      Serial.print("ECO_RETORNO:");
      Serial.println(cmd.substring(4));
    }
    else if (cmd.length() > 0) {
      Serial.print("RECEBIDO_DESCONHECIDO:");
      Serial.println(cmd);
    }
  }

  // 2. Heartbeat a cada 2s para provar que esta vivo
  if (millis() - ultimoHeartbeat > 2000) {
    ultimoHeartbeat = millis();
    Serial.print("ARDUINO VIVO em ");
    Serial.print(millis() / 1000);
    Serial.println("s");
  }
}
