# Galeria de Evidências

## Parte 1: ESP32 no Wokwi

Gerados por `scripts/teste_wokwi.py`. Registro completo: [Monitor Serial](wokwi_monitor_serial.txt).

### Circuito em execução, online
![Circuito](wokwi_circuito.png)

### Taquicardia: LED vermelho aceso
![Taquicardia no Wokwi](wokwi_alerta_taquicardia.png)

### Sem conexão: LEDs acesos e fila crescendo
![Offline](wokwi_serial_offline.png)

### Conexão de volta: fila enviada com `"replay":true`
![Sincronização](wokwi_serial_sync.png)

## Parte 2: Dashboard recebendo o ESP32 do Wokwi

### Sinais normais
![Normal](dashboard_esp32_normal.png)

### Taquicardia
![Taquicardia](dashboard_esp32_taquicardia.png)

### Febre
![Febre](dashboard_esp32_febre.png)

### Dispositivo offline
![Offline](dashboard_esp32_offline.png)

### Reconexão: dados recuperados no horário original
![Replay](dashboard_esp32_replay.png)

### Imobilidade (nível de atenção)
![Imobilidade](dashboard_esp32_imobilidade.png)

## Parte 2: Dashboard recebendo o simulador Python

Gerados por `scripts/capture_evidencias.py`. Os dados vêm de `scripts/simula_esp32.py`, que publica o mesmo JSON do firmware, e não do ESP32.

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
