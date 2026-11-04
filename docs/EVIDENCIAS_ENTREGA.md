# Evidências da Entrega

## O que falta o grupo fazer

- [ ] Assistir ao vídeo do Ir Além 2 (2:55, narração por voz neural sintética), em [video/cardioia_ir_alem_2.mp4](../video/cardioia_ir_alem_2.mp4). Se preferirem narrar, o roteiro está em [VIDEO_SCRIPT_4MIN.md](VIDEO_SCRIPT_4MIN.md).
- [ ] Publicar o vídeo no YouTube como **não listado**, colar o link no [README](../README.md) e testar em uma janela anônima.
- [ ] Confirmar nomes e RMs no README.
- [ ] Opcional: abrir o [projeto no Wokwi](https://wokwi.com/projects/479712047921435649) com a conta do grupo, salvar uma cópia e trocar o link no README. O projeto atual foi salvo sem login e não pertence a nenhuma conta, portanto vocês não conseguem editá-lo pela conta do grupo. Ele é público: o modo não listado do Wokwi é pago.

## Como refazer as evidências

Com o Node-RED rodando (`cd dashboard/node-red && npm start`):

```bash
python scripts/teste_wokwi.py          # ESP32 no Wokwi: cerca de 6 minutos
python scripts/capture_evidencias.py   # Simulador Python: cerca de 2 minutos
```

Os dois scripts conferem o comportamento e falham em vez de salvar um print enganoso. `teste_wokwi.py` depende da interface do site do Wokwi; se ela mudar, o roteiro manual abaixo faz o mesmo.

### Roteiro manual no Wokwi

Deixe o dashboard aberto em `http://localhost:1880/ui`.

1. O Monitor Serial mostra `[LEITURA]` a cada 5 s e `[REDE] MQTT conectado`. Uma falha inicial com "estado -4" é normal: há nova tentativa em 5 s.
2. Envie `b80`: o LED do painel fica verde.
3. Envie `b130`: o LED vermelho do circuito acende e o painel mostra taquicardia.
4. Envie `b0` e aperte o botão azul em ritmo constante: o BPM segue o ritmo.
5. Clique no DHT22 e suba a temperatura acima de 38 °C: o painel mostra febre.
6. Mova o switch para a direita: LED amarelo aceso, painel "Offline" e `fila=` crescendo.
7. Depois de uns 30 s, volte o switch: linhas `[CLOUD]` com `"replay":true` esvaziam a fila.
8. Sem movimento por 2 minutos, surge o alerta de imobilidade em amarelo. É o esperado, porque o acelerômetro do Wokwi começa parado; altere a aceleração no MPU6050 para limpar.

## O que cada verificação cobre

| Item | Como foi verificado |
|---|---|
| Firmware no Wokwi | Executado no site; projeto salvo idêntico ao repositório |
| Broker e dashboard | ESP32 no Wokwi → HiveMQ público → Node-RED |
| Fila cheia e descarte | Testes no computador, não no Wokwi |
| SPIFFS e TLS | Apenas compilados: sem chip físico nem cluster HiveMQ Cloud |
