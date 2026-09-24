// Teste comunicacao Arduino <-> Raspberry Pi via Cabo USB / Serial
const int vermelho = 2;
const int verde = 3;
const int azul = 4;

#define LED_PIN 13

void setup() {
  pinMode(vermelho, OUTPUT);
  pinMode(azul, OUTPUT);
  pinMode(verde, OUTPUT);

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  Serial.begin(115200);
  while (!Serial) { ; } // espera no Leonardo/Micro
  Serial.println("ARDUINO PRONTO");
}

void cores(int r, int g, int b){
  analogWrite(vermelho, r);
  analogWrite(verde, g);
  analogWrite(azul, b);
}

void loop() {
  // 1. Recebe comandos do Raspberry
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    cmd.toUpperCase();

    if (cmd == "VERMELHO") {
      cores(255, 0, 0);
    }
    else if (cmd == "AZUL") {
      cores(0, 0, 255);
    }
    else if (cmd == "VERDE") {
      cores(0, 255, 0);
    }
    else if (cmd == "LED_OFF") {
      digitalWrite(LED_PIN, LOW);
      Serial.println("OK LED OFF");
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
}
