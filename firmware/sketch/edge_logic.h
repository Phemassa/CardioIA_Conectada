// edge_logic.h — Processamento local do wearable, em C++ puro (sem Arduino).
// Fica separado do sketch para ser testado no computador: ver tests/test_edge_logic.cpp.
#pragma once
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

namespace cardioia {

enum FlagsAmostra : uint8_t {
  ALERTA_TAQUICARDIA = 1 << 0,
  ALERTA_BRADICARDIA = 1 << 1,
  ALERTA_FEBRE = 1 << 2,
  ALERTA_IMOBILIDADE = 1 << 3,
  // Amostra veio do SPIFFS apos reinicio: millis() recomecou, entao a idade e desconhecida.
  AMOSTRA_BOOT_ANTERIOR = 1 << 7,
};

// Alertas que acendem o LED vermelho e que o buffer tenta nunca descartar.
// Imobilidade fica de fora: e "atencao", nao emergencia (o paciente pode estar dormindo).
const uint8_t MASCARA_CRITICOS = ALERTA_TAQUICARDIA | ALERTA_BRADICARDIA | ALERTA_FEBRE;

// Valores que indicam "sensor sem leitura valida" (ex.: o DHT22 devolveu NaN).
const int16_t TEMP_INVALIDA = INT16_MIN;
const uint16_t VALOR_INVALIDO = 0xFFFF;

// 16 bytes por amostra: inteiros em decimos no lugar de float para caber mais no buffer.
struct Amostra {
  uint32_t seq;          // Numero sequencial: permite ao assinante perceber lacunas
  uint32_t capturadaMs;  // millis() no momento da captura
  int16_t tempDecimos;   // 36,6 C -> 366
  uint16_t umidDecimos;  // 55,0 % -> 550
  uint16_t movMg;        // Pico de desvio de 1 g no periodo, em mili-g
  uint8_t bpm;           // 0 = sem sinal
  uint8_t flags;         // Combinacao de FlagsAmostra
};

struct Limites {
  int bpmAlto;
  int bpmBaixo;
  int tempFebreDecimos;
  uint32_t imobilidadeMs;
};

// Decide os alertas no proprio dispositivo: funcionam mesmo sem internet.
inline uint8_t avaliarAlertas(const Amostra& a, const Limites& lim, uint32_t msSemMovimento) {
  uint8_t flags = 0;
  if (a.bpm > lim.bpmAlto) flags |= ALERTA_TAQUICARDIA;
  // bpm == 0 e "sem sinal" (ninguem apertando o botao), nao bradicardia. Num produto
  // real isso viraria um alerta proprio de sensor desconectado.
  if (a.bpm > 0 && a.bpm < lim.bpmBaixo) flags |= ALERTA_BRADICARDIA;
  if (a.tempDecimos != TEMP_INVALIDA && a.tempDecimos > lim.tempFebreDecimos) flags |= ALERTA_FEBRE;
  if (a.movMg != VALOR_INVALIDO && msSemMovimento > lim.imobilidadeMs) flags |= ALERTA_IMOBILIDADE;
  return flags;
}

// Estima o BPM pela media dos ultimos intervalos entre batidas (como o intervalo RR).
class EstimadorBpm {
 public:
  explicit EstimadorBpm(uint32_t timeoutMs = 5000) : timeoutMs_(timeoutMs) {}

  void registrarBatida(uint32_t agoraMs) {
    // Pausa longa: os intervalos antigos nao descrevem mais o ritmo atual.
    if (n_ > 0 && agoraMs - batidas_[(pos_ + N - 1) % N] > timeoutMs_) n_ = 0;
    batidas_[pos_] = agoraMs;
    pos_ = (pos_ + 1) % N;
    if (n_ < N) n_++;
  }

  uint8_t bpm(uint32_t agoraMs) const {
    if (n_ < 2) return 0;
    uint32_t ultima = batidas_[(pos_ + N - 1) % N];
    if (agoraMs - ultima > timeoutMs_) return 0;
    uint32_t primeira = batidas_[(pos_ + N - n_) % N];
    uint32_t intervaloMedio = (ultima - primeira) / (n_ - 1);
    if (intervaloMedio == 0) return 0;
    uint32_t valor = 60000UL / intervaloMedio;
    return valor > 255 ? 255 : (uint8_t)valor;
  }

 private:
  static const size_t N = 6;  // 6 batidas = media de 5 intervalos
  uint32_t batidas_[N] = {0};
  size_t pos_ = 0;
  size_t n_ = 0;
  uint32_t timeoutMs_;
};

// Fila circular de tamanho fixo (sem alocacao dinamica) onde as amostras esperam envio.
// Cheia, descarta a amostra NORMAL mais antiga: alertas criticos sao os ultimos a sair.
template <size_t CAPACIDADE>
class FilaResiliente {
 public:
  void inserir(const Amostra& a) {
    if (tamanho_ == CAPACIDADE) descartarUma();
    dados_[(inicio_ + tamanho_) % CAPACIDADE] = a;
    tamanho_++;
  }

  bool vazia() const { return tamanho_ == 0; }
  size_t tamanho() const { return tamanho_; }
  uint32_t descartadas() const { return descartadas_; }

  // i = 0 e a amostra mais antiga.
  const Amostra& em(size_t i) const { return dados_[(inicio_ + i) % CAPACIDADE]; }

  // So chamar depois de confirmar o envio: a amostra nunca sai da fila antes disso.
  void removerMaisAntiga() {
    if (tamanho_ == 0) return;
    inicio_ = (inicio_ + 1) % CAPACIDADE;
    tamanho_--;
  }

 private:
  void descartarUma() {
    size_t alvo = 0;  // Se todas forem criticas, sai a mais antiga
    for (size_t i = 0; i < tamanho_; i++) {
      if (!(em(i).flags & MASCARA_CRITICOS)) {
        alvo = i;
        break;
      }
    }
    // Empurra as mais antigas uma posicao, cobrindo o alvo e preservando a ordem.
    for (size_t i = alvo; i > 0; i--) {
      dados_[(inicio_ + i) % CAPACIDADE] = dados_[(inicio_ + i - 1) % CAPACIDADE];
    }
    inicio_ = (inicio_ + 1) % CAPACIDADE;
    tamanho_--;
    descartadas_++;
  }

  Amostra dados_[CAPACIDADE];
  size_t inicio_ = 0;
  size_t tamanho_ = 0;
  uint32_t descartadas_ = 0;
};

// Escreve decimos como decimal ("-0.5", "36.6"), tratando o sinal de valores entre -1 e 0.
inline void formatarDecimos(char* dest, size_t tam, int valor) {
  int absoluto = valor < 0 ? -valor : valor;
  snprintf(dest, tam, "%s%d.%d", valor < 0 ? "-" : "", absoluto / 10, absoluto % 10);
}

// Monta o JSON publicado. Em vez de relogio, envia a idade da amostra ("age_s"): quem
// recebe calcula o horario real (chegada - idade), sem o ESP32 depender de NTP.
// Retorna o tamanho escrito, ou -1 se nao couber em buf.
inline int formatarJson(char* buf, size_t tam, const Amostra& a, const char* dispositivo,
                        uint32_t agoraMs, size_t naFila, uint32_t replayAPartirDeS) {
  char temp[12] = "null", umid[12] = "null", mov[8] = "null", idade[12] = "null";
  if (a.tempDecimos != TEMP_INVALIDA) formatarDecimos(temp, sizeof(temp), a.tempDecimos);
  if (a.umidDecimos != VALOR_INVALIDO) formatarDecimos(umid, sizeof(umid), a.umidDecimos);
  if (a.movMg != VALOR_INVALIDO) snprintf(mov, sizeof(mov), "%u", (unsigned)a.movMg);

  bool bootAnterior = a.flags & AMOSTRA_BOOT_ANTERIOR;
  uint32_t idadeS = (agoraMs - a.capturadaMs) / 1000;
  if (!bootAnterior) snprintf(idade, sizeof(idade), "%lu", (unsigned long)idadeS);
  bool replay = bootAnterior || idadeS >= replayAPartirDeS;

  char alertas[64] = "";
  size_t p = 0;
  const struct {
    uint8_t flag;
    const char* nome;
  } NOMES[] = {
      {ALERTA_TAQUICARDIA, "TAQUICARDIA"},
      {ALERTA_BRADICARDIA, "BRADICARDIA"},
      {ALERTA_FEBRE, "FEBRE"},
      {ALERTA_IMOBILIDADE, "IMOBILIDADE"},
  };
  for (const auto& n : NOMES) {
    if (a.flags & n.flag) {
      p += snprintf(alertas + p, sizeof(alertas) - p, "%s\"%s\"", p ? "," : "", n.nome);
    }
  }

  int escrito = snprintf(buf, tam,
                         "{\"dev\":\"%s\",\"seq\":%lu,\"age_s\":%s,\"temp_c\":%s,\"umid_pct\":%s,"
                         "\"bpm\":%u,\"mov_mg\":%s,\"alertas\":[%s],\"replay\":%s,\"fila\":%u}",
                         dispositivo, (unsigned long)a.seq, idade, temp, umid, (unsigned)a.bpm, mov,
                         alertas, replay ? "true" : "false", (unsigned)naFila);
  return (escrito < 0 || (size_t)escrito >= tam) ? -1 : escrito;
}

}  // namespace cardioia
