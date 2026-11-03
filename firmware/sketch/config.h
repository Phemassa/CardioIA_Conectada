// config.h — Parametros do wearable CardioIA (Fase 3).
// Tudo o que o grupo pode querer ajustar fica aqui; a logica nao tem numeros soltos.
#pragma once

// ---------- Identificacao (pseudonimo: nunca dado identificavel de paciente) ----------
#define DISPOSITIVO_ID "wearable-01"

// ---------- Pinos (ver diagram.json) ----------
#define PINO_DHT 15          // DHT22: temperatura + umidade (conta como 1 sensor)
#define PINO_BOTAO_BPM 4     // Botao de pressao: cada toque = 1 batimento
#define PINO_SWITCH_WIFI 27  // Slide switch: esquerda = online, direita = offline
#define PINO_LED_ALERTA 25   // LED vermelho: alerta critico
#define PINO_LED_OFFLINE 26  // LED amarelo: sem nuvem, gravando no buffer
// MPU6050 (movimento) usa o I2C padrao do ESP32: SDA=21, SCL=22.

// ---------- Temporizacao ----------
#define INTERVALO_AMOSTRA_MS 5000UL  // 1 amostra a cada 5 s (DHT22 pede no minimo 2 s)
#define INTERVALO_MOVIMENTO_MS 200UL // MPU6050 lido 5x/s para nao perder movimentos curtos
#define DEBOUNCE_BOTAO_MS 60UL
#define REPLAY_A_PARTIR_DE_S 10UL    // Amostra com idade >= 10 s e marcada "replay":true

// ---------- Limites clinicos (definidos pelo grupo; repetidos no Node-RED e na API) ----------
#define LIM_BPM_ALTO 120             // Taquicardia: bpm > 120
#define LIM_BPM_BAIXO 50             // Bradicardia: 0 < bpm < 50
#define LIM_TEMP_FEBRE_DECIMOS 380   // Febre: temperatura > 38,0 C
#define LIM_MOV_MG 50                // Abaixo de 50 mg de desvio de 1 g = parado
// Para a demonstracao, 2 min. Em uso real seria da ordem de dezenas de minutos.
#define LIM_IMOBILIDADE_MS 120000UL

// ---------- Resiliencia offline ----------
// 4000 amostras x 5 s = 5 h 33 min sem conexao, ocupando 4000 x 16 bytes = 64 kB de RAM.
// 5000 amostras (80 kB) nao cabem: o link falha por estouro da DRAM estatica do ESP32.
// Justificativa em docs/RELATORIO_PARTE_1.md.
#define CAPACIDADE_BUFFER 4000
#define MAX_ENVIOS_POR_CICLO 10      // Sincroniza aos poucos para nao travar a coleta

// SPIFFS sobrevive a queda de energia, mas so no chip real: nos simuladores ele e
// volatil. Desligado por padrao; o ambiente esp32-real do platformio.ini liga.
#ifndef CARDIOIA_USE_SPIFFS
#define CARDIOIA_USE_SPIFFS 0
#endif
#define ARQUIVO_OFFLINE "/offline.bin"

// ---------- Rede ----------
// Wokwi-GUEST e a rede aberta do simulador; o canal 6 evita a varredura (~4 s).
#define WIFI_SSID "Wokwi-GUEST"
#define WIFI_SENHA ""
#define WIFI_CANAL 6

// Broker publico da HiveMQ: sem cadastro nem criptografia. Qualquer pessoa pode ler
// estes topicos, por isso so trafega dado sintetico e pseudonimizado.
// Para HiveMQ Cloud (TLS + usuario/senha): copie secrets.exemplo.h para secrets.h.
#if __has_include("secrets.h")
#include "secrets.h"
#endif
#ifndef MQTT_HOST
#define MQTT_HOST "broker.hivemq.com"
#endif
#ifndef MQTT_USE_TLS
#define MQTT_USE_TLS 0
#endif
#ifndef MQTT_PORTA
#define MQTT_PORTA (MQTT_USE_TLS ? 8883 : 1883)
#endif
#ifndef MQTT_USUARIO
#define MQTT_USUARIO nullptr
#endif
#ifndef MQTT_SENHA
#define MQTT_SENHA nullptr
#endif

#define TOPICO_BASE "cardioia/grupo-zion/" DISPOSITIVO_ID
#define TOPICO_TELEMETRIA TOPICO_BASE "/telemetria"
#define TOPICO_STATUS TOPICO_BASE "/status"
