// Testes da logica de borda do firmware, executados no computador (sem ESP32).
// Compilar e rodar: ver "Testes" no README.md.
#include <stdio.h>
#include <string.h>

#include "../firmware/sketch/edge_logic.h"

using namespace cardioia;

static int falhas = 0;
#define CHECK(cond)                                         \
  do {                                                      \
    if (!(cond)) {                                          \
      printf("FALHOU %s:%d: %s\n", __FILE__, __LINE__, #cond); \
      falhas++;                                             \
    }                                                       \
  } while (0)

static const Limites LIM = {120, 50, 380, 120000};

static Amostra amostra(uint32_t seq, uint8_t flags = 0) {
  Amostra a = {};
  a.seq = seq;
  a.tempDecimos = 366;
  a.umidDecimos = 550;
  a.bpm = 72;
  a.flags = flags;
  return a;
}

static void testaTamanhoDaAmostra() {
  // A capacidade anunciada nos relatorios depende destes 16 bytes.
  CHECK(sizeof(Amostra) == 16);
}

static void testaAlertas() {
  Amostra a = amostra(1);
  CHECK(avaliarAlertas(a, LIM, 0) == 0);

  a.bpm = 120;  // No limite ainda nao e alerta: a regra e bpm > 120
  CHECK(avaliarAlertas(a, LIM, 0) == 0);
  a.bpm = 121;
  CHECK(avaliarAlertas(a, LIM, 0) == ALERTA_TAQUICARDIA);
  a.bpm = 49;
  CHECK(avaliarAlertas(a, LIM, 0) == ALERTA_BRADICARDIA);
  a.bpm = 0;  // Sem sinal nao e bradicardia
  CHECK(avaliarAlertas(a, LIM, 0) == 0);

  a = amostra(2);
  a.tempDecimos = 380;
  CHECK(avaliarAlertas(a, LIM, 0) == 0);
  a.tempDecimos = 381;
  CHECK(avaliarAlertas(a, LIM, 0) == ALERTA_FEBRE);
  a.tempDecimos = TEMP_INVALIDA;  // Sensor com falha nao gera alerta falso
  CHECK(avaliarAlertas(a, LIM, 0) == 0);

  a = amostra(3);
  CHECK(avaliarAlertas(a, LIM, 120000) == 0);
  CHECK(avaliarAlertas(a, LIM, 120001) == ALERTA_IMOBILIDADE);
  a.movMg = VALOR_INVALIDO;  // Sem acelerometro nao da para afirmar imobilidade
  CHECK(avaliarAlertas(a, LIM, 999999) == 0);
}

static void testaBpm() {
  EstimadorBpm e(5000);
  CHECK(e.bpm(0) == 0);  // Nenhuma batida
  e.registrarBatida(1000);
  CHECK(e.bpm(1000) == 0);  // Uma batida nao forma intervalo

  uint32_t t = 1000;
  for (int i = 0; i < 10; i++) {
    t += 500;  // 1 batida a cada 500 ms = 120 bpm
    e.registrarBatida(t);
  }
  CHECK(e.bpm(t) == 120);
  CHECK(e.bpm(t + 5000) == 120);
  CHECK(e.bpm(t + 5001) == 0);  // Parou de bater: sem sinal

  // Depois de uma pausa, o ritmo novo nao pode ser diluido pelos intervalos antigos.
  t += 20000;
  e.registrarBatida(t);
  e.registrarBatida(t + 1000);
  CHECK(e.bpm(t + 1000) == 60);

  // Atravessar o estouro de millis() (49 dias) nao pode quebrar o calculo.
  EstimadorBpm w(5000);
  uint32_t inicio = 0xFFFFFFFFUL - 700;
  w.registrarBatida(inicio);
  w.registrarBatida(inicio + 1000);
  CHECK(w.bpm(inicio + 1000) == 60);
}

static void testaFilaFifo() {
  FilaResiliente<3> f;
  CHECK(f.vazia());
  f.removerMaisAntiga();  // Remover de fila vazia nao pode corromper o estado
  CHECK(f.tamanho() == 0);

  f.inserir(amostra(1));
  f.inserir(amostra(2));
  CHECK(f.em(0).seq == 1);
  f.removerMaisAntiga();
  f.inserir(amostra(3));
  f.inserir(amostra(4));  // Da a volta no vetor interno
  CHECK(f.tamanho() == 3);
  CHECK(f.em(0).seq == 2);
  CHECK(f.em(1).seq == 3);
  CHECK(f.em(2).seq == 4);
  CHECK(f.descartadas() == 0);
}

static void testaDescartePreservaCriticos() {
  FilaResiliente<4> f;
  f.inserir(amostra(1, ALERTA_FEBRE));
  f.inserir(amostra(2));  // Normal mais antiga: e esta que deve sair
  f.inserir(amostra(3, ALERTA_TAQUICARDIA));
  f.inserir(amostra(4));
  f.inserir(amostra(5));

  CHECK(f.tamanho() == 4);
  CHECK(f.descartadas() == 1);
  CHECK(f.em(0).seq == 1);
  CHECK(f.em(1).seq == 3);
  CHECK(f.em(2).seq == 4);
  CHECK(f.em(3).seq == 5);

  // Imobilidade e so atencao: pode ser descartada antes de uma critica.
  FilaResiliente<2> g;
  g.inserir(amostra(1, ALERTA_FEBRE));
  g.inserir(amostra(2, ALERTA_IMOBILIDADE));
  g.inserir(amostra(3));
  CHECK(g.em(0).seq == 1);
  CHECK(g.em(1).seq == 3);

  // Todas criticas: sai a mais antiga e a fila continua aceitando.
  FilaResiliente<2> h;
  h.inserir(amostra(1, ALERTA_FEBRE));
  h.inserir(amostra(2, ALERTA_FEBRE));
  h.inserir(amostra(3, ALERTA_FEBRE));
  CHECK(h.em(0).seq == 2);
  CHECK(h.em(1).seq == 3);
}

static void testaFilaCheiaPorMuitoTempo() {
  // Equivale a muitas horas offline na capacidade real: nunca passa do limite.
  static FilaResiliente<4000> f;
  for (uint32_t i = 0; i < 20000; i++) {
    f.inserir(amostra(i, i % 100 == 0 ? ALERTA_TAQUICARDIA : 0));
  }
  CHECK(f.tamanho() == 4000);
  CHECK(f.descartadas() == 16000);
  // As 200 amostras criticas (1 a cada 100) sobrevivem, e a ordem segue crescente.
  int criticas = 0;
  for (size_t i = 0; i < f.tamanho(); i++) {
    if (f.em(i).flags & MASCARA_CRITICOS) criticas++;
    if (i > 0) CHECK(f.em(i).seq > f.em(i - 1).seq);
  }
  CHECK(criticas == 200);
}

static void testaJson() {
  char buf[256];
  Amostra a = amostra(7, ALERTA_TAQUICARDIA | ALERTA_FEBRE);
  a.capturadaMs = 1000;
  a.movMg = 12;
  a.tempDecimos = 386;
  CHECK(formatarJson(buf, sizeof(buf), a, "w1", 4000, 2, 10) > 0);
  CHECK(strcmp(buf,
               "{\"dev\":\"w1\",\"seq\":7,\"age_s\":3,\"temp_c\":38.6,\"umid_pct\":55.0,\"bpm\":72,"
               "\"mov_mg\":12,\"alertas\":[\"TAQUICARDIA\",\"FEBRE\"],\"replay\":false,\"fila\":2}") == 0);

  // Idade grande vira replay
  formatarJson(buf, sizeof(buf), a, "w1", 11000, 0, 10);
  CHECK(strstr(buf, "\"age_s\":10,") && strstr(buf, "\"replay\":true"));

  // Sensor com falha vira null (JSON valido, nunca nan)
  Amostra b = amostra(8);
  b.tempDecimos = TEMP_INVALIDA;
  b.umidDecimos = VALOR_INVALIDO;
  b.movMg = VALOR_INVALIDO;
  formatarJson(buf, sizeof(buf), b, "w1", 0, 0, 10);
  CHECK(strstr(buf, "\"temp_c\":null,\"umid_pct\":null") && strstr(buf, "\"mov_mg\":null"));
  CHECK(strstr(buf, "\"alertas\":[]"));

  // Vinda de um boot anterior: idade desconhecida
  Amostra c = amostra(9, AMOSTRA_BOOT_ANTERIOR);
  formatarJson(buf, sizeof(buf), c, "w1", 0, 0, 10);
  CHECK(strstr(buf, "\"age_s\":null") && strstr(buf, "\"replay\":true"));

  // Temperatura negativa entre -1 e 0 mantem o sinal
  Amostra d = amostra(10);
  d.tempDecimos = -5;
  formatarJson(buf, sizeof(buf), d, "w1", 0, 0, 10);
  CHECK(strstr(buf, "\"temp_c\":-0.5,"));

  // Pior caso cabe nos 256 bytes do sketch, e buffer curto e detectado.
  Amostra e = amostra(0xFFFFFFFFUL, 0x8F);
  e.flags = ALERTA_TAQUICARDIA | ALERTA_BRADICARDIA | ALERTA_FEBRE | ALERTA_IMOBILIDADE;
  e.tempDecimos = -3276;
  e.umidDecimos = 65534;
  e.movMg = 65534;
  e.bpm = 255;
  int tam = formatarJson(buf, sizeof(buf), e, "wearable-01", 0xFFFFFFFFUL, 4000, 10);
  CHECK(tam > 0 && tam < 256);
  char curto[16];
  CHECK(formatarJson(curto, sizeof(curto), e, "wearable-01", 0, 0, 10) == -1);
  printf("Maior JSON: %d bytes\n", tam);
}

int main() {
  testaTamanhoDaAmostra();
  testaAlertas();
  testaBpm();
  testaFilaFifo();
  testaDescartePreservaCriticos();
  testaFilaCheiaPorMuitoTempo();
  testaJson();
  if (falhas) {
    printf("%d verificacao(oes) falharam\n", falhas);
    return 1;
  }
  printf("OK: todos os testes de edge_logic passaram\n");
  return 0;
}
