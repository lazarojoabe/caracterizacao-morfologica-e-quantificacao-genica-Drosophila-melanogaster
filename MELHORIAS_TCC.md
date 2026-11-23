# Melhorias implementadas no pipeline

## Objetivo

Esta versão revisada foi criada para transformar o protótipo da iniciação científica em um pipeline mais adequado ao TCC, mantendo os scripts originais intactos para permitir uma comparação reprodutível.

O método original continua representado por `aplicaGaussianoEOtsu.py`, `detectaBordas.py`, `preencheNucleos.py` e `obtemMediaProteina.py`. O novo método está em `pipeline_melhorado.py` e a comparação está em `comparar_resultados.py`.

## Alterações implementadas

### 1. Pareamento robusto

O novo pipeline normaliza os sufixos `_z0_ch00.tif`, `_z0_ch02.tif`, `_ch00.tif` e `_ch02.tif`. Isso recupera o par `Image007`, que era ignorado pelo código original.

O arquivo `manifesto_amostras.csv` registra todos os arquivos pareados e incompletos.

### 2. Seleção explícita dos canais

O núcleo é lido pelo canal azul (`channel=0`) e a proteína pelo canal vermelho (`channel=2`), preservando a intensidade original de 8 bits. A nova implementação não converte a proteína para tons de cinza antes da quantificação.

### 3. Máscara monocanal e segmentação individual

O pipeline aplica Gaussian, Otsu, abertura/fechamento morfológico e remoção de componentes menores que `min_nucleus_area`. Depois, cada componente conectado recebe um identificador próprio.

As máscaras são mantidas como imagens binárias monocanais. Sobreposições coloridas são usadas apenas para controle visual.

### 4. Quantificação no interior do núcleo

Para cada núcleo são calculados área, média, mediana, desvio-padrão e intensidade integrada, diretamente sobre os pixels internos da máscara.

O resultado está em `resultados_por_nucleo.csv`. A média por amostra é calculada a partir das médias dos núcleos, sem misturar todos os contornos em uma única lista.

### 5. Validações de entrada e saída

O pipeline verifica leitura das imagens, compatibilidade de dimensões, existência de canais, nomes duplicados e falhas de gravação.

### 6. Reprodutibilidade

Os parâmetros utilizados são salvos em `configuracao.json`. O processamento pode ser executado pela linha de comando e gera resultados tabulares, manifesto e imagens de controle de qualidade.

## Execução

```text
python pipeline_melhorado.py --verbose
python comparar_resultados.py
```

Parâmetros úteis:

```text
python pipeline_melhorado.py --min-nucleus-area 100
```

## Arquivos gerados

- `resultados_tcc/manifesto_amostras.csv`: pares de imagens e status.
- `resultados_tcc/resultados_por_nucleo.csv`: medidas individuais.
- `resultados_tcc/resumo_por_amostra.csv`: resumo por imagem.
- `resultados_tcc/comparativo_amostras.csv`: comparação amostra a amostra.
- `resultados_tcc/comparativo_resultados.md`: resumo textual da comparação.
- `resultados_tcc/comparativo_resumo.json`: estatísticas numéricas da comparação.
- `resultados_tcc/mascaras_melhoradas/`: máscaras binárias por amostra.
- `resultados_tcc/overlays_melhorados/`: imagens para inspeção visual.

## Testes

Os testes de regressão em `test_pipeline_melhorado.py` verificam os dois formatos de nome de arquivo, a existência dos 43 pares completos e a presença de sinal nos canais selecionados.

```text
python -m unittest -v test_pipeline_melhorado.py
```

## Limitações que permanecem como trabalho experimental

1. A segmentação ainda precisa ser validada contra máscaras anotadas manualmente.
2. O limiar de área mínima e os kernels morfológicos devem ser ajustados usando um conjunto de validação, não apenas pelo resultado visual.
3. Núcleos encostados podem exigir watershed para separar instâncias.
4. O registro espacial entre os canais deve ser validado caso as imagens tenham sido adquiridas/exportadas separadamente.

Essas limitações estão explicitadas para evitar que a nova versão seja apresentada como validada biologicamente antes da etapa de ground truth.
