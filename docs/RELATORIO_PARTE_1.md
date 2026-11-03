# Relatório da Parte 1: Armazenamento e Processamento Local (Edge Computing)

**CardioIA Conectada, Grupo Zion**

## 1. Objetivo

Um wearable cardíaco não pode depender da internet para funcionar. Se o Wi-Fi da casa do paciente cai durante a madrugada, os batimentos daquele período continuam importando para o médico, principalmente se houve uma crise. Esta parte implementa no ESP32 a coleta, a decisão local de alertas e a retenção dos dados até a conexão voltar.

## 2. Sensores

| Sensor | Mede | Papel no projeto |
|---|---|---|
| **DHT22** (obrigatório) | Temperatura e umidade | Detecta febre |
| **Botão de pressão** | Batimentos: cada toque é uma batida | Detecta taquicardia e bradicardia |
| **MPU6050** (adicional) | Aceleração | Detecta ausência de movimento |

O enunciado pede ao menos dois sensores; o MPU6050 foi acrescentado para cobrir o movimento citado no objetivo geral. O BPM é calculado pela média dos últimos cinco intervalos entre toques, de forma análoga ao intervalo RR de um ECG. Se nenhum toque chega em 5 s, o BPM vira 0, tratado como "sem sinal" e não como bradicardia.

## 3. Fluxo de funcionamento

A cada 5 segundos, o `loop()` executa estes passos:

1. **Captura:** lê temperatura e umidade, calcula o BPM e pega o pico de movimento do período. O acelerômetro é lido 5 vezes por segundo para não perder movimentos curtos.
2. **Processamento local:** compara os valores com os limites clínicos e grava os alertas na própria amostra. O LED vermelho acende nos alertas críticos, com ou sem internet.
3. **Enfileiramento:** a amostra sempre entra na fila, inclusive quando há conexão.
4. **Sincronização:** se houver conexão, até 10 amostras saem da fila por ciclo, da mais antiga para a mais nova. Cada envio aparece no Monitor Serial com o prefixo `[CLOUD]`, como pede o enunciado, e também é publicado por MQTT.

Essa decisão de projeto simplifica a resiliência: **não existe um caminho "online" e outro "offline"**. A sincronização depois de uma queda é o funcionamento normal, só que com a fila mais cheia. Assim, o caminho de recuperação é exercitado em toda amostra, e não apenas nos raros momentos de falha.

A conectividade simulada é a variável booleana `wifiSimulado`, controlada por um *slide switch* no circuito. Com o switch à direita, o sistema se comporta como desconectado: o LED amarelo acende e a fila cresce.

## 4. Lógica de resiliência

**Quando apagar.** Uma amostra só sai da fila depois que `mqtt.publish()` retorna sucesso. Se o envio falhar, ela permanece e a tentativa se repete no ciclo seguinte.

**Quanto guardar.** A fila tem **4.000 amostras**. A 1 amostra a cada 5 s, são **5 horas e 33 minutos** sem conexão, o suficiente para quedas domésticas comuns e para boa parte de uma madrugada. Cada amostra ocupa 16 bytes, pois os valores são guardados como inteiros em décimos, totalizando 64 kB.

O número veio de um limite medido. O plano inicial era de 5.000 amostras (quase 7 horas), mas a compilação falhou: a memória estática do ESP32 estourou por 1.424 bytes. Com 4.000 amostras, o firmware compila usando 33,6% da RAM. A alocação é estática de propósito, porque assim o limite aparece na compilação, e não como um travamento no paciente horas depois.

**O que descartar.** Com a fila cheia, sai a amostra **normal** mais antiga, e não simplesmente a mais antiga de todas. O dado que o médico mais precisa ver é a crise, e ele não deve ser perdido para dar lugar a horas de ritmo normal. Se todas forem críticas, sai a mais antiga. Um teste com 20.000 amostras em uma fila de 4.000 confirma que as 200 amostras críticas sobrevivem e que a ordem cronológica se mantém.

**Como manter o horário.** O ESP32 não depende de relógio ou NTP. Cada mensagem informa a idade da amostra (`age_s`), e quem recebe calcula o horário real: chegada menos idade.

**Armazenamento persistente (SPIFFS).** Como o enunciado alerta, o SPIFFS é volátil nos simuladores; por isso, no Wokwi a fila fica em RAM e o Monitor Serial serve de registro offline. O ambiente `esp32-real` do PlatformIO ativa um diário em SPIFFS: ele replica a fila em disco, recarrega as amostras após uma queda de energia e apaga o arquivo quando a fila esvazia. Esse código foi compilado, mas **não executado**, por falta de um chip físico.

## 5. Como foi verificado

| Verificação | Resultado |
|---|---|
| Compilação com PlatformIO (Wokwi, chip real com SPIFFS, TLS) | Sucesso nas três; alvo Wokwi usa 33,6% da RAM e 59,8% da flash |
| Testes da lógica de borda no computador ([test_edge_logic.cpp](../tests/test_edge_logic.cpp)) | Todos passam: limites, BPM, fila, descarte, JSON |
| Maior JSON possível | 201 bytes, abaixo do limite de 256 |
| Execução no Wokwi | **Pendente:** exige login do grupo ([passo a passo](EVIDENCIAS_ENTREGA.md)) |

## 6. Limitações

- Sem SPIFFS, uma reinicialização do ESP32 perde a fila que está em RAM.
- A confirmação de envio é só do cliente MQTT local. Com QoS 0 não há aviso de entrega pelo broker, então uma queda no momento exato do envio pode perder a amostra.
- O botão simula o batimento; ele não mede um coração real. O alerta de imobilidade usa 2 minutos para caber em uma demonstração, e em uso real o valor seria maior.
- BPM igual a 0 não gera alerta. Num produto real, sensor sem sinal precisaria de um alerta próprio.
