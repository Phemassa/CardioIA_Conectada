/*
 * CardioIA — Fase 3: Monitoramento Continuo (IoT no Peito do Paciente)
 * Wearable simulado com ESP32. Fluxo: captura -> processamento local -> fila -> MQTT.
 *
 * Toda amostra entra na fila antes de qualquer envio; online ou offline, o caminho e o
 * mesmo. Por isso a sincronizacao apos uma queda nao precisa de codigo especial: a fila
 * apenas esvazia, da mais antiga para a mais nova.
 *
 * Comandos pelo Monitor Serial: b130 (simula 130 bpm), b0 (volta ao botao), s (status).
 */
#include <Adafruit_MPU6050.h>
#include <DHT.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <Wire.h>
#include <math.h>

#include "config.h"
#include "edge_logic.h"

#if CARDIOIA_USE_SPIFFS
#include <SPIFFS.h>
#endif

using namespace cardioia;

DHT dht(PINO_DHT, DHT22);
Adafruit_MPU6050 mpu;
bool mpuOk = false;

#if MQTT_USE_TLS
WiFiClientSecure clienteRede;
#else
WiFiClient clienteRede;
#endif
PubSubClient mqtt(clienteRede);

const Limites LIMITES = {LIM_BPM_ALTO, LIM_BPM_BAIXO, LIM_TEMP_FEBRE_DECIMOS, LIM_IMOBILIDADE_MS};

// static: os 64 kB ficam reservados na compilacao, sem risco de faltar heap em execucao.
static FilaResiliente<CAPACIDADE_BUFFER> fila;
EstimadorBpm estimador;

uint32_t proximoSeq = 0;
bool wifiSimulado = true;  // A variavel booleana de conectividade pedida no enunciado
bool mqttEstavaConectado = false;
uint32_t ultimaAmostraMs = 0, ultimaLeituraMovMs = 0, ultimoMovimentoMs = 0;
uint32_t ultimaTentativaMqttMs = 0;
uint16_t picoMovMg = 0;
uint32_t simBpm = 0, proximaBatidaSimMs = 0;

// A interrupcao so guarda o instante do toque; o calculo do BPM fica no loop().
// A fila e grande o bastante para os ate 5 s que uma tentativa de conexao pode bloquear.
const uint8_t TAM_FILA_BATIDAS = 32;
volatile uint32_t batidasIsr[TAM_FILA_BATIDAS];
volatile uint8_t batidasEscrita = 0;
uint8_t batidasLeitura = 0;

void IRAM_ATTR aoApertarBotao() {
  static uint32_t ultimoToqueMs = 0;
  uint32_t agora = millis();
  if (agora - ultimoToqueMs < DEBOUNCE_BOTAO_MS) return;
  ultimoToqueMs = agora;
  batidasIsr[batidasEscrita] = agora;
  batidasEscrita = (batidasEscrita + 1) % TAM_FILA_BATIDAS;
}

void processarBatidas(uint32_t agora) {
  while (batidasLeitura != batidasEscrita) {
    estimador.registrarBatida(batidasIsr[batidasLeitura]);
    batidasLeitura = (batidasLeitura + 1) % TAM_FILA_BATIDAS;
  }
  if (simBpm > 0 && (int32_t)(agora - proximaBatidaSimMs) >= 0) {
    estimador.registrarBatida(agora);
    proximaBatidaSimMs = agora + 60000UL / simBpm;
  }
}

// Le o acelerometro varias vezes por amostra e guarda o pico de desvio de 1 g (repouso).
void lerMovimento(uint32_t agora) {
  if (!mpuOk) return;
  sensors_event_t acc, giro, temp;
  mpu.getEvent(&acc, &giro, &temp);
  float g = sqrtf(acc.acceleration.x * acc.acceleration.x + acc.acceleration.y * acc.acceleration.y +
                  acc.acceleration.z * acc.acceleration.z) / 9.80665f;
  uint16_t desvioMg = (uint16_t)(fabsf(g - 1.0f) * 1000.0f);
  if (desvioMg > picoMovMg) picoMovMg = desvioMg;
  if (desvioMg >= LIM_MOV_MG) ultimoMovimentoMs = agora;
}

#if CARDIOIA_USE_SPIFFS
// Diario em disco: replica a fila para sobreviver a queda de energia (so no chip real).
uint32_t registrosNoDiario = 0;

void diarioAnexar(const Amostra& a) {
  File f = SPIFFS.open(ARQUIVO_OFFLINE, FILE_APPEND);
  if (!f) return;
  f.write((const uint8_t*)&a, sizeof(a));
  f.close();
  registrosNoDiario++;
  // O arquivo so cresce enquanto offline; se dobrar a capacidade, regrava so o que vale.
  if (registrosNoDiario >= 2 * CAPACIDADE_BUFFER) {
    File c = SPIFFS.open(ARQUIVO_OFFLINE, FILE_WRITE);
    if (!c) return;
    for (size_t i = 0; i < fila.tamanho(); i++) c.write((const uint8_t*)&fila.em(i), sizeof(Amostra));
    c.close();
    registrosNoDiario = fila.tamanho();
  }
}

void diarioCarregar() {
  File f = SPIFFS.open(ARQUIVO_OFFLINE, FILE_READ);
  if (!f) return;
  Amostra a;
  while (f.read((uint8_t*)&a, sizeof(a)) == sizeof(a)) {
    a.flags |= AMOSTRA_BOOT_ANTERIOR;
    fila.inserir(a);
    registrosNoDiario++;
    if (a.seq >= proximoSeq) proximoSeq = a.seq + 1;
  }
  f.close();
  Serial.printf("[EDGE] %u amostras recuperadas do SPIFFS\n", (unsigned)fila.tamanho());
}

void diarioApagar() {
  if (registrosNoDiario == 0) return;
  SPIFFS.remove(ARQUIVO_OFFLINE);
  registrosNoDiario = 0;
  Serial.println("[EDGE] Fila vazia: arquivo local apagado");
}
#endif

void coletarAmostra(uint32_t agora) {
  Amostra a = {};
  a.seq = proximoSeq++;
  a.capturadaMs = agora;

  float t = dht.readTemperature();
  float u = dht.readHumidity();
  a.tempDecimos = isnan(t) ? TEMP_INVALIDA : (int16_t)lroundf(t * 10);
  a.umidDecimos = isnan(u) ? VALOR_INVALIDO : (uint16_t)lroundf(u * 10);
  a.movMg = mpuOk ? picoMovMg : VALOR_INVALIDO;
  a.bpm = estimador.bpm(agora);
  a.flags = avaliarAlertas(a, LIMITES, agora - ultimoMovimentoMs);
  picoMovMg = 0;

  fila.inserir(a);
#if CARDIOIA_USE_SPIFFS
  diarioAnexar(a);
#endif

  // O Monitor Serial e tambem o registro offline nos simuladores, onde SPIFFS nao persiste.
  Serial.printf("[LEITURA] seq=%lu t=%.1fC u=%.1f%% bpm=%u mov=%umg flags=0x%02X fila=%u/%u\n",
                (unsigned long)a.seq, t, u, a.bpm, a.movMg, a.flags, (unsigned)fila.tamanho(),
                CAPACIDADE_BUFFER);

  digitalWrite(PINO_LED_ALERTA, (a.flags & MASCARA_CRITICOS) ? HIGH : LOW);
}

void manterConexaoMqtt(uint32_t agora) {
  if (mqtt.connected()) return;
  if (mqttEstavaConectado) {
    mqttEstavaConectado = false;
    Serial.println("[REDE] Conexao MQTT perdida: seguindo no buffer local");
  }
  if (WiFi.status() != WL_CONNECTED) return;
  if (agora - ultimaTentativaMqttMs < 5000) return;
  ultimaTentativaMqttMs = agora;

  // ID unico: num broker publico, um ID repetido derruba a outra sessao.
  char clientId[40];
  snprintf(clientId, sizeof(clientId), "cardioia-%s-%08lx", DISPOSITIVO_ID, (unsigned long)esp_random());

  // Last Will: se o ESP32 sumir sem avisar, o proprio broker publica "offline".
  if (mqtt.connect(clientId, MQTT_USUARIO, MQTT_SENHA, TOPICO_STATUS, 1, true, "offline")) {
    mqttEstavaConectado = true;
    mqtt.publish(TOPICO_STATUS, "online", true);
    Serial.printf("[REDE] MQTT conectado em %s:%d; %u amostras a sincronizar\n", MQTT_HOST, MQTT_PORTA,
                  (unsigned)fila.tamanho());
  } else {
    Serial.printf("[REDE] Falha no MQTT (estado %d); nova tentativa em 5 s\n", mqtt.state());
  }
}

// Envia ate MAX_ENVIOS_POR_CICLO amostras, da mais antiga para a mais nova.
void sincronizarFila(uint32_t agora) {
  char json[256];
  for (int i = 0; i < MAX_ENVIOS_POR_CICLO && !fila.vazia(); i++) {
    const Amostra& a = fila.em(0);
    int tam = formatarJson(json, sizeof(json), a, DISPOSITIVO_ID, agora, fila.tamanho() - 1,
                           REPLAY_A_PARTIR_DE_S);
    if (tam < 0) {  // Nao deve ocorrer: 256 bytes cabem o maior JSON possivel
      Serial.println("[EDGE] JSON excede o buffer: amostra descartada");
      fila.removerMaisAntiga();
      continue;
    }
    if (!mqtt.publish(TOPICO_TELEMETRIA, json)) return;  // Falhou: a amostra fica na fila

    Serial.print("[CLOUD] ");  // "Envio para a nuvem via Serial.println" da Parte 1
    Serial.println(json);
    fila.removerMaisAntiga();
    mqtt.loop();
  }
#if CARDIOIA_USE_SPIFFS
  if (fila.vazia()) diarioApagar();
#endif
}

void atualizarSwitchWifi() {
  bool novo = digitalRead(PINO_SWITCH_WIFI) == HIGH;
  if (novo == wifiSimulado) return;
  wifiSimulado = novo;
  if (!wifiSimulado && mqtt.connected()) {
    // Desconexao "limpa" nao dispara o Last Will, entao avisamos o status antes de sair.
    mqtt.publish(TOPICO_STATUS, "offline", true);
    mqtt.disconnect();
  }
  ultimaTentativaMqttMs = millis() - 5000;  // Ao religar, tenta na hora
  Serial.printf("[REDE] Wi-Fi simulado: %s\n", wifiSimulado ? "CONECTADO" : "DESCONECTADO");
}

void imprimirStatus() {
  Serial.printf("[STATUS] wifi_sim=%d wifi=%d mqtt=%d fila=%u/%u descartadas=%lu sim_bpm=%lu heap=%u\n",
                wifiSimulado, WiFi.status() == WL_CONNECTED, mqtt.connected(), (unsigned)fila.tamanho(),
                CAPACIDADE_BUFFER, (unsigned long)fila.descartadas(), (unsigned long)simBpm,
                ESP.getFreeHeap());
}

void lerComandosSerial(uint32_t agora) {
  if (!Serial.available()) return;
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  if (cmd == "s") {
    imprimirStatus();
  } else if (cmd.startsWith("b")) {
    long valor = cmd.substring(1).toInt();
    simBpm = (valor > 0 && valor <= 250) ? (uint32_t)valor : 0;
    proximaBatidaSimMs = agora;
    Serial.printf("[SIM] Batimento simulado: %lu bpm (0 = usar o botao)\n", (unsigned long)simBpm);
  }
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(20);  // readStringUntil nao pode segurar a coleta
  Serial.println("\n[CardioIA] Wearable iniciando. Comandos: b130, b0, s");

  pinMode(PINO_LED_ALERTA, OUTPUT);
  pinMode(PINO_LED_OFFLINE, OUTPUT);
  // Pull-up: switch a esquerda deixa o pino em HIGH (online); a direita o liga ao GND.
  pinMode(PINO_SWITCH_WIFI, INPUT_PULLUP);
  wifiSimulado = digitalRead(PINO_SWITCH_WIFI) == HIGH;
  pinMode(PINO_BOTAO_BPM, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PINO_BOTAO_BPM), aoApertarBotao, FALLING);

  dht.begin();
  mpuOk = mpu.begin();
  if (mpuOk) mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  else Serial.println("[EDGE] MPU6050 nao encontrado: seguindo sem movimento");
  ultimoMovimentoMs = millis();

#if CARDIOIA_USE_SPIFFS
  if (SPIFFS.begin(true)) diarioCarregar();
  else Serial.println("[EDGE] SPIFFS indisponivel: buffer somente em RAM");
#endif

#if MQTT_USE_TLS
  // Demonstracao: criptografa, mas nao valida o certificado. Em producao, use setCACert().
  clienteRede.setInsecure();
#endif
  mqtt.setServer(MQTT_HOST, MQTT_PORTA);
  mqtt.setBufferSize(320);   // O padrao de 256 bytes nao cabe JSON + topico + cabecalho
  mqtt.setSocketTimeout(5);  // Limita quanto a conexao pode bloquear a coleta

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_SENHA, WIFI_CANAL);  // Nao bloqueia: a coleta comeca ja
}

void loop() {
  uint32_t agora = millis();

  lerComandosSerial(agora);
  atualizarSwitchWifi();
  processarBatidas(agora);

  if (agora - ultimaLeituraMovMs >= INTERVALO_MOVIMENTO_MS) {
    ultimaLeituraMovMs = agora;
    lerMovimento(agora);
  }
  if (agora - ultimaAmostraMs >= INTERVALO_AMOSTRA_MS) {
    ultimaAmostraMs = agora;
    coletarAmostra(agora);
  }

  if (wifiSimulado) {
    manterConexaoMqtt(agora);
    if (mqtt.connected()) {
      mqtt.loop();
      sincronizarFila(agora);
    }
  }
  digitalWrite(PINO_LED_OFFLINE, mqtt.connected() ? LOW : HIGH);

  delay(5);
}
