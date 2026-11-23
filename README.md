# Caracterização morfológica e quantificação da expressão gênica em imagens sagitais da Drosophila melanogaster

Nesse repositório estão os materiais usados e desenvolvidos na minha iniciação científica, realizada na Universidade Federal de Uberlândia.

Em síntese, o propósito do trabalho é, dadas duas imagens – sendo uma contendo
os núcleos e a outra, suas respectivas proteínas –, detectar a expressão gênica de cada
elemento. Essa tarefa foi alcançada tomando os seguintes passos:
• Primeiramente, dada uma imagem de núcleos, o programa procura entre o DataSet
de imagens de proteínas aquela que contém a expressão gênica desses núcleos em
questão.

• Em seguida, ambas as imagens são convertidas de RGB para escala de cinza, visando
otimizar o processamento computacional. Nesse caso, como são utilizados 8 bits de
profundidade, ao converter para escala de cinza, é possível representar 256 níveis de
intensidade. Assim, essas variam entre 0 e 255.

• Após isso, é necessário binarizar a imagem de núcleos. Para essa tarefa, é aplicado
um filtro Gaussiano para a redução de ruídos e o algoritmo de Otsu, com o fito de
encontrar o threshold ótimo. Assim, é obtido uma imagem binária, isto é, contendo
somente dois tons: preto e branco.

• Vale salientar que foi experimentado utilizar o operador de Sobel para essa tarefa,
entretanto os resultados obtidos não foram satisfatórios. Desse modo, optou-se a
utilizar o método proposto por Canny, que utiliza do operador de Sobel em seus
passos.

• Com as bordas jé detectadas, fez-se o uso das funções findContours e drawCon-
tours para localizar os pontos das arestas, obtendo assim as suas coordenadas. Após
isso, essas mesmas ferramentas são utilizadas nos pontos internos a esses contornos,
preenchendo os núcleos.

• Tendo obtido acesso aos pixels de cada núcleo, é feito uma pesquisa de intensidade
na imagem de proteínas (em escala de cinza) usando as coordenadas desses pixels.
Simultaneamente em que são obtidos os valores de intensidade presentes nas proteí-
nas (que quantificam a expressão gênica), eles são adicionados a uma estrutura de
dados individual de cada imagem analisada.

• Ao fim, é possível verificar a intensidade em que a proteína foi expressa em cada
núcleo.

• Para servir de métrica geral, foi tomada a média aritmética da intensidade de pro-
teína expressa em cada imagem.

## Versão revisada para o TCC

O arquivo `pipeline_melhorado.py` implementa uma versão revisada e reproduzível do
pipeline, com pareamento robusto, seleção explícita do canal vermelho da proteína,
segmentação individual dos núcleos, quantificação dos pixels internos e exportação dos
resultados em CSV. O script `comparar_resultados.py` gera o
comparativo entre o método original e o método revisado. Todas as alterações e as
limitações que ainda exigem validação estão documentadas em `MELHORIAS_TCC.md`.

## Interface local de revisão

O repositório também contém uma aplicação web local em `backend/` e
`frontend/`. O backend reutiliza `read_channel` e `segment_nuclei` do
`pipeline_melhorado.py`; métricas, persistência, histórico e API ficam em
módulos separados para preservar o CLI existente.

### Arquitetura

```text
frontend/                 React + TypeScript + Vite + Tailwind
  src/api.ts              cliente HTTP/SSE
  src/components/         canvas, métricas e tabela
backend/app/
  main.py                 FastAPI e contratos HTTP
  processing/              leitura, algoritmo adaptador e métricas
  services/                sessões, jobs, edições e undo/redo
  repositories/            SQLite para metadados e histórico
.nuclei_data/              criado em runtime; uploads e banco local
pipeline_melhorado.py     CLI preservado e referência de segmentação
```

### Instalação e execução

No diretório raiz:

```text
python -m pip install -r requirements.txt
python -m uvicorn backend.app.main:app --reload --port 8000
```

Em outro terminal:

```text
cd frontend
npm install
npm run dev
```

Abra `http://localhost:5173`. O assistente define canais, escala espacial,
tipo de entrada e parâmetros iniciais. O upload usa nomes sanitizados, limite
de tamanho e não aceita caminhos arbitrários do cliente.

O processamento ocorre em pool limitado de workers e a sessão mantém revisão
otimista. Ocultar só muda a visualização; excluir/restaurar atualiza agregados
com métricas em cache; editar contorno recalcula apenas o núcleo escolhido.
Conflitos retornam HTTP 409. Ctrl/Cmd+Z e Ctrl/Cmd+Y fazem undo/redo. CSV e
JSON ficam disponíveis na barra superior.

Imagens com `_border`, `_mask`, `_overlay`, `binarizada`, `gaussian` ou `filled`
são marcadas como derivadas e geram aviso, pois overlays podem ter alterado os
pixels e não equivalem ao sinal bruto. Pré-visualizações são normalizadas só
para desenho; a quantificação usa os arrays decodificados da sessão.

### Métricas

Área é a quantidade de pixels da máscara; área espacial é `área_px ×
pixel_size²`. Centroide vem dos momentos binários. Perímetro é o contorno
externo; raio equivalente é `sqrt(área/π)` e diâmetro é duas vezes esse raio.
Eixos são ajustados por elipse quando há pelo menos cinco pontos;
excentricidade é `sqrt(1 - (eixo_menor/eixo_maior)²)`. Circularidade é
`4π × área / perímetro²`. Médias, mediana, desvio-padrão e intensidade
integrada usam pixels internos. A quantificação utiliza diretamente a intensidade do
canal de proteína selecionado, sem correção por uma média de fundo.

### Testes

```text
python -m unittest -v test_pipeline_melhorado.py
python -m pytest backend/tests -q
cd frontend
npm test
npm run build
```

As limitações biológicas de `MELHORIAS_TCC.md` continuam válidas: ground truth
manual, separação de núcleos encostados e validação do registro espacial entre canais
ainda são necessários.
