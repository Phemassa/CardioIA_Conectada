# Roteiro do Vídeo: Ir Além 2 (até 4 minutos)

Publicar no YouTube como **não listado** e colar o link no README. Tela: notebook aberto, rolando conforme a fala.

O vídeo gerado usa este roteiro como base, com ajustes para a voz sintética: "dispositivo vestível" no lugar de "wearable" e "área sob a curva" no lugar de "AUC-PR".

## 0:00 a 0:30 | O problema

> Somos o Grupo Zion, do projeto CardioIA. O wearable da nossa Fase 3 mede o intervalo entre batimentos. A pergunta aqui é: só com esses intervalos, dá para detectar trechos com arritmia? E uma rede neuromórfica compete com um modelo tradicional?

**Mostrar:** a introdução do notebook.

## 0:30 a 1:15 | Dados e cuidado principal

> Usamos a base MIT-BIH, com batimentos anotados por cardiologistas. Cada exemplo tem 32 batimentos e é anormal se pelo menos 10% forem ectópicos. O cuidado mais importante foi separar treino e teste por paciente: se a mesma pessoa aparecesse nos dois lados, o modelo reconheceria o paciente e as métricas sairiam otimistas. Até a divisão padrão da literatura deixava os registros 201 e 202, da mesma pessoa, em lados opostos. Então tiramos o 202 do teste.

**Mostrar:** a tabela de janelas e o gráfico de séries normais e anormais.

## 1:15 a 2:00 | Os modelos

> Comparamos três modelos. Uma regressão logística sobre sete medidas clínicas de variabilidade. A mesma regressão sobre a série bruta. E um reservatório de 200 neurônios LIF, que acumulam corrente e disparam ao cruzar um limiar. Os pesos entre eles são aleatórios e fixos: só a camada de saída é treinada.

**Mostrar:** a fórmula do LIF e, em seguida, o gráfico de spikes. Apontar que a janela anormal dispara bem mais.

## 2:00 a 3:00 | Resultados

> A regressão com atributos ganhou: AUC-PR de 0,849 contra 0,724 do LIF, e a diferença se sustenta, com intervalo de confiança pareado de 0,044 a 0,222. Já a regressão sobre a série bruta atingiu 99% de sensibilidade, mas marcando quase tudo como anormal, com especificidade inferior a 1%: um número alto que não vale nada. Olhando paciente a paciente, o registro 213 foi quase todo perdido pela regressão e também foi mal no LIF. Uma avaliação só pela média esconderia isso.

**Mostrar:** a tabela final, as curvas e a tabela por paciente.

## 3:00 a 3:45 | Análise crítica

> O LIF tem atividade esparsa, o que interessa ao hardware neuromórfico, mas em nossa simulação custou cerca de 640 vezes mais operações. Isso é uma estimativa, porque não temos esse hardware. E nosso resultado não prova que redes neuromórficas são piores: avaliamos só um reservatório sem treino interno. Os intervalos também vêm de anotações de especialistas, e um wearable real erraria batimentos. Com isso em mente, nada aqui serve para uso clínico.

**Mostrar:** a tabela de custos e a seção de limitações.

## 3:45 a 4:00 | Conclusão

> Para este problema, recomendamos a regressão logística: melhor, interpretável e leve o bastante para o próprio ESP32. Às vezes, o modelo simples é a resposta certa. Obrigado!
