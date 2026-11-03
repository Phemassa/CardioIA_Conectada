# Checklist de Barema

Legenda: ✅ pronto e verificado · ⏳ depende de ação do grupo · ➖ opcional não feito

## Critérios principais (10 pontos)

| Critério | Pontos | Status | Evidência |
|---|---|---|---|
| Leitura de sensores | 2 | ⏳ Código compila e a lógica está testada; falta rodar no Wokwi | [sketch.ino](../firmware/sketch/sketch.ino) |
| Resiliência offline (Edge) | 2 | ⏳ Lógica da fila testada no computador; falta rodar no Wokwi | [edge_logic.h](../firmware/sketch/edge_logic.h), [testes](../tests/test_edge_logic.cpp) |
| Envio via MQTT e broker | 2 | ⏳ Broker e assinatura testados com o simulador; falta o ESP32 publicar pelo Wokwi | [Relatório Parte 2](RELATORIO_PARTE_2.md) |
| Dashboard funcional e alertas | 2 | ✅ Sete cenários conferidos no painel real | [prints](../assets/evidencias/README.md) |
| Documentação (código + relatórios) | 2 | ✅ Código comentado e quatro relatórios | [docs](.) |

## Entregáveis

### Parte 1

- [ ] ⏳ Link do projeto no Wokwi
- [x] Código C++ comentado
- [x] Relatório de fluxo e resiliência (mínimo de 1 página): [Parte 1](RELATORIO_PARTE_1.md)
- [x] DHT22 + segundo sensor (botão), mais MPU6050
- [x] Conectividade simulada por variável booleana (switch)
- [x] Envio pelo Serial e remoção da amostra enviada
- [x] Estratégia de armazenamento limitado: 4.000 amostras
- [x] SPIFFS (opcional): implementado para chip real; compilado, não executado

### Parte 2

- [x] Código do ESP32
- [x] Envio via MQTT (HiveMQ)
- [x] Gráfico, gauge e indicador de alerta no Node-RED
- [x] Export do dashboard: [flows.json](../dashboard/node-red/flows.json)
- [x] Prints do dashboard, recebendo o simulador Python
- [ ] ⏳ Print do dashboard recebendo o ESP32 no Wokwi
- [x] Relatório MQTT e dashboard (mínimo de 2 páginas): [Parte 2](RELATORIO_PARTE_2.md)
- ➖ Grafana Cloud (opcional)

### Ir Além 1

- [x] Cliente REST em Python: envio e recebimento
- [x] Lógica de risco: taquicardia, bradicardia, febre e ausência de movimento
- [x] Simulação de e-mail automatizado, com opção de SMTP real
- [x] Relatório: [Ir Além 1](RELATORIO_IR_ALEM_1.md)

### Ir Além 2

- [x] Notebook comentado: [ir_alem_2_series_temporais.ipynb](../notebooks/ir_alem_2_series_temporais.ipynb)
- [ ] ⏳ Repositório GitHub público com código e README (falta publicar)
- [x] Relatório comparativo: [Ir Além 2](RELATORIO_IR_ALEM_2.md)
- [ ] ⏳ Vídeo de até 4 minutos, não listado, com link no README: [roteiro](VIDEO_SCRIPT_4MIN.md)

Passos pendentes em detalhe: [EVIDENCIAS_ENTREGA.md](EVIDENCIAS_ENTREGA.md).
