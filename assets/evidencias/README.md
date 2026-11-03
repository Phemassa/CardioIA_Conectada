# Galeria de Evidências

**Origem:** os prints do dashboard foram gerados por `scripts/capture_evidencias.py`, com o Node-RED real ligado ao broker público da HiveMQ. Os dados vêm do **simulador Python** (`scripts/simula_esp32.py`), que publica o mesmo JSON do firmware, e não do ESP32. Os prints do Wokwi estão pendentes: ver [docs/EVIDENCIAS_ENTREGA.md](../../docs/EVIDENCIAS_ENTREGA.md).

## Parte 2: Dashboard

### Sinais normais
![Normal](dashboard_01_normal.png)

### Taquicardia
![Taquicardia](dashboard_02_taquicardia.png)

### Febre
![Febre](dashboard_03_febre.png)

### Dispositivo offline
![Offline](dashboard_04_offline.png)

### Reconexão: dados recuperados no horário original
![Replay](dashboard_05_replay.png)

### Imobilidade (nível de atenção)
![Imobilidade](dashboard_06_imobilidade.png)

### Sem leituras: o painel avisa em vez de congelar
![Sem dados](dashboard_07_sem_dados.png)

## Ir Além 1: API REST e e-mail

- [Saída do cliente REST](ir_alem_1_execucao.txt)
- [E-mail de alerta gerado](ir_alem_1_email_exemplo.eml)

## Ir Além 2: Séries temporais

### Janelas normais e anormais
![Séries](ir_alem_2_series.png)

### Curvas em pacientes fora do treino
![Curvas](ir_alem_2_curvas.png)

### Atividade da rede LIF
![Raster](ir_alem_2_raster.png)
