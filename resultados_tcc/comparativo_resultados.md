# Comparativo do método original e do método melhorado

Os valores foram calculados nos pares comuns ao baseline e ao pipeline revisado.

- Pares medidos pelo método original: **42**.
- Pares processados pelo método melhorado: **43**.
- Amostras sem resultado no baseline: **1**.
- Média original (tons de cinza no contorno): **20.202**.
- Média revisada (canal vermelho, interior): **60.724**.
- Mudança absoluta média: **40.522**.
- Mudança relativa média: **202.50%**.
- Contornos no baseline: **46.95** por imagem; núcleos no método revisado: **39.48** por imagem.

A diferença inclui três mudanças deliberadas: canal vermelho bruto, pixels do interior e identificação individual dos núcleos. Portanto, ela não deve ser interpretada como simples ganho/perda de desempenho numérico; trata-se de uma mudança na definição da medida.
