# Evidências da Entrega: o que falta o grupo fazer

Tudo o que dependia só de código está pronto. Os passos abaixo exigem a conta ou a voz de alguém do grupo.

## 1. Criar o projeto no Wokwi

Tempo estimado: 10 minutos. **O firmware compila, mas nunca foi executado no simulador; este é o primeiro teste real dele.**

1. Entre em https://wokwi.com, faça login e crie um projeto **ESP32** novo.
2. Na aba `sketch.ino`, cole o conteúdo de [firmware/sketch/sketch.ino](../firmware/sketch/sketch.ino).
3. Na aba `diagram.json`, substitua tudo pelo conteúdo de [firmware/sketch/diagram.json](../firmware/sketch/diagram.json).
4. Crie os arquivos `config.h` e `edge_logic.h` (seta ao lado das abas → *New file*) e cole o conteúdo dos arquivos de mesmo nome.
5. Crie `libraries.txt` com o conteúdo de [firmware/sketch/libraries.txt](../firmware/sketch/libraries.txt).
6. Clique em **Save** e rode. Ajuste a posição das peças no desenho, se preferir; os fios podem ficar sobrepostos porque as coordenadas foram definidas sem visualizar o circuito.
7. Copie o link e cole no [README](../README.md), na tabela "Links da Entrega".

Também é possível usar a extensão Wokwi do VS Code: `cd firmware/sketch && pio run -e wokwi`.

### Roteiro de teste no Wokwi

Deixe o dashboard aberto em `http://localhost:1880/ui`. Marque cada item conforme testar; **se algo falhar, anote a saída do Monitor Serial.**

- [ ] O Monitor Serial mostra `[LEITURA]` a cada 5 s e `[REDE] MQTT conectado`.
- [ ] O LED amarelo apaga depois de conectar, e o painel mostra "Online".
- [ ] Envie `b80`: o BPM fica em torno de 80 e o LED do painel fica verde.
- [ ] Envie `b130`: o LED vermelho do circuito acende e o painel mostra taquicardia.
- [ ] Envie `b0` e aperte o botão azul umas 6 vezes em ritmo constante: o BPM segue o ritmo.
- [ ] Suba o DHT22 acima de 38 °C: o painel mostra febre.
- [ ] Mova o switch para a direita: LED amarelo aceso, painel "Offline" e `fila=` crescendo no Serial.
- [ ] Depois de uns 2 minutos, volte o switch: linhas `[CLOUD]` com `"replay":true` esvaziam a fila, e os pontos aparecem no gráfico no horário original.
- [ ] Sem mexer no MPU6050 por 2 minutos, o alerta de imobilidade aparece em amarelo. É o esperado, porque o acelerômetro do Wokwi começa parado; mude a aceleração para limpar.

## 2. Prints a capturar

Salve em `assets/evidencias/` e adicione à [galeria](../assets/evidencias/README.md).

- [ ] `wokwi_circuito.png`: circuito com a simulação rodando.
- [ ] `wokwi_serial_online.png`: Monitor Serial com `[LEITURA]` e `[CLOUD]`.
- [ ] `wokwi_serial_offline.png`: fila crescendo com o switch desligado.
- [ ] `wokwi_serial_sync.png`: sincronização com `"replay":true`.
- [ ] `dashboard_esp32.png`: painel recebendo dados do ESP32, não do simulador Python.

O script `scripts/capture_evidencias.py` refaz os prints do dashboard automaticamente, usando o simulador.

## 3. Gravar o vídeo do Ir Além 2

- [ ] Gravar seguindo o [roteiro](VIDEO_SCRIPT_4MIN.md), com até 4 minutos.
- [ ] Publicar no YouTube como **não listado**.
- [ ] Colar o link no [README](../README.md).
- [ ] Testar o link em uma janela anônima.

## 4. Antes de enviar

- [ ] Repositório público no GitHub (exigência do Ir Além 2).
- [ ] Confirmar nomes e RMs no README.
- [ ] Nenhum `TODO(humano)` restante: pesquise "TODO" no README.
- [ ] Reler os relatórios: eles descrevem o firmware como "não executado no Wokwi". Depois do teste, atualize a Parte 1 (seção 5), a Parte 2 (seção 4) e o Status do README com o que foi observado.
